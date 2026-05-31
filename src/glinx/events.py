from __future__ import annotations

import ast
import math
import statistics
from collections import defaultdict, deque
from typing import Any

from .config import EventRuleConfig, SummaryWindowConfig
from .models import EventMessage, GlinxMessage


class SafeExpressionEvaluator(ast.NodeVisitor):
    allowed_functions = {"abs": abs, "min": min, "max": max, "round": round}
    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.BoolOp,
        ast.Compare,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Call,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.And,
        ast.Or,
        ast.Eq,
        ast.NotEq,
        ast.Gt,
        ast.GtE,
        ast.Lt,
        ast.LtE,
    )

    def __init__(self, variables: dict[str, Any]) -> None:
        self.variables = variables

    def visit(self, node: ast.AST) -> Any:
        if not isinstance(node, self.allowed_nodes):
            raise ValueError(f"Unsupported expression node: {type(node).__name__}")
        return super().visit(node)

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Name(self, node: ast.Name) -> Any:
        return self.variables.get(node.id, 0)

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Unsupported call target")
        fn = self.allowed_functions.get(node.func.id)
        if fn is None:
            raise ValueError(f"Unsupported function: {node.func.id}")
        args = [self.visit(arg) for arg in node.args]
        return fn(*args)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        value = self.visit(node.operand)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return +value
        raise ValueError("Unsupported unary operator")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            return left**right
        raise ValueError("Unsupported binary operator")

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        values = [self.visit(value) for value in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise ValueError("Unsupported boolean operator")

    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        for operator, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            if isinstance(operator, ast.Gt) and not left > right:
                return False
            if isinstance(operator, ast.GtE) and not left >= right:
                return False
            if isinstance(operator, ast.Lt) and not left < right:
                return False
            if isinstance(operator, ast.LtE) and not left <= right:
                return False
            if isinstance(operator, ast.Eq) and not left == right:
                return False
            if isinstance(operator, ast.NotEq) and not left != right:
                return False
            left = right
        return True


def safe_eval(expression: str, variables: dict[str, Any]) -> bool:
    tree = ast.parse(expression, mode="eval")
    return bool(SafeExpressionEvaluator(variables).visit(tree))


class EventFilter:
    def __init__(
        self,
        rules: list[EventRuleConfig],
        summary_windows: list[SummaryWindowConfig],
        window_size: int = 20,
        z_threshold: float = 2.5,
    ) -> None:
        self.rules = rules
        self.summary_windows = summary_windows
        self.window_size = window_size
        self.z_threshold = z_threshold
        self._numeric_history: dict[str, dict[str, deque[float]]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=window_size))
        )
        self._last_summary_at: dict[str, float] = {}

    def process(self, message: GlinxMessage) -> list[EventMessage]:
        events: list[EventMessage] = []
        events.extend(self._rule_events(message))
        events.extend(self._anomaly_events(message))
        events.extend(self._summary_events(message))
        self._update_history(message)
        return events

    def _rule_events(self, message: GlinxMessage) -> list[EventMessage]:
        variables = dict(message.enriched)
        variables.update(message.parsed)
        events: list[EventMessage] = []
        for rule in self.rules:
            if rule.sensor != message.source_id:
                continue
            if safe_eval(rule.condition, variables):
                events.append(
                    EventMessage(
                        source_id=message.source_id,
                        label=rule.label,
                        priority=rule.priority,
                        timestamp=message.timestamp,
                        kind="rule",
                        description=f"Rule triggered: {rule.condition}",
                        payload=message.enriched,
                    )
                )
        return events

    def _anomaly_events(self, message: GlinxMessage) -> list[EventMessage]:
        events: list[EventMessage] = []
        history = self._numeric_history[message.source_id]
        for key, value in message.enriched.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            series = history[key]
            if len(series) < 5:
                continue
            std_dev = statistics.pstdev(series)
            if math.isclose(std_dev, 0.0):
                continue
            mean = statistics.fmean(series)
            z_score = abs((value - mean) / std_dev)
            if z_score >= self.z_threshold:
                events.append(
                    EventMessage(
                        source_id=message.source_id,
                        label=f"{key}_anomaly",
                        priority="MEDIUM",
                        timestamp=message.timestamp,
                        kind="anomaly",
                        description=f"{key} deviated from rolling mean with z={z_score:.2f}",
                        payload={"field": key, "value": value, "mean": mean, "z_score": z_score},
                    )
                )
        return events

    def _summary_events(self, message: GlinxMessage) -> list[EventMessage]:
        events: list[EventMessage] = []
        for window in self.summary_windows:
            if message.source_id not in window.sensors:
                continue
            last_seen = self._last_summary_at.get(window.label, 0.0)
            if message.timestamp - last_seen < window.interval_seconds:
                continue
            self._last_summary_at[window.label] = message.timestamp
            events.append(
                EventMessage(
                    source_id=message.source_id,
                    label=window.label,
                    priority="LOW",
                    timestamp=message.timestamp,
                    kind="summary",
                    description=message.enriched.get(
                        "semantic_summary",
                        f"Summary window update from {message.source_id}",
                    ),
                    payload=message.enriched,
                )
            )
        return events

    def _update_history(self, message: GlinxMessage) -> None:
        history = self._numeric_history[message.source_id]
        for key, value in message.enriched.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                history[key].append(float(value))
