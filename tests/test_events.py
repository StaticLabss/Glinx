"""Tests for the event filtering subsystem."""

import math

import pytest

from glinx.events import EventFilter, SafeExpressionEvaluator, safe_eval
from glinx.config import EventRuleConfig, SummaryWindowConfig
from glinx.models import GlinxMessage


# ── SafeExpressionEvaluator tests ───────────────────────────────


def test_safe_eval_basic_comparison() -> None:
    assert safe_eval("x > 5", {"x": 10}) is True
    assert safe_eval("x > 5", {"x": 3}) is False


def test_safe_eval_boolean_operators() -> None:
    assert safe_eval("x > 0 and y > 0", {"x": 1, "y": 2}) is True
    assert safe_eval("x > 0 and y > 0", {"x": 1, "y": -1}) is False
    assert safe_eval("x > 0 or y > 0", {"x": -1, "y": 1}) is True


def test_safe_eval_allowed_functions() -> None:
    assert safe_eval("abs(x) > 5", {"x": -10}) is True
    assert safe_eval("min(x, y) < 0", {"x": -1, "y": 5}) is True
    assert safe_eval("max(x, y) > 10", {"x": 5, "y": 15}) is True
    assert safe_eval("round(x) == 3", {"x": 3.4}) is True


def test_safe_eval_arithmetic() -> None:
    assert safe_eval("x + y > 10", {"x": 6, "y": 7}) is True
    assert safe_eval("x * 2 == 10", {"x": 5}) is True
    assert safe_eval("x ** 2 > 20", {"x": 5}) is True


def test_safe_eval_missing_var_defaults_to_zero() -> None:
    # This is current behavior — missing vars default to 0.
    assert safe_eval("missing_var > 5", {}) is False
    assert safe_eval("missing_var == 0", {}) is True


def test_safe_eval_rejects_disallowed_nodes() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        safe_eval("__import__('os')", {})


def test_safe_eval_rejects_disallowed_function() -> None:
    with pytest.raises(ValueError, match="Unsupported function"):
        safe_eval("len('hello') > 3", {})


def test_safe_eval_chained_comparison() -> None:
    assert safe_eval("1 < x < 10", {"x": 5}) is True
    assert safe_eval("1 < x < 10", {"x": 15}) is False


# ── EventFilter rule tests ─────────────────────────────────────


def _make_message(source_id: str, enriched: dict, ts: float = 1000.0) -> GlinxMessage:
    return GlinxMessage(
        source_id=source_id,
        protocol="mock",
        timestamp=ts,
        parsed=enriched,
        enriched=enriched,
    )


def test_rule_event_fires_on_match() -> None:
    rules = [EventRuleConfig(sensor="s1", condition="temp > 50", priority="HIGH", label="hot")]
    ef = EventFilter(rules, [])
    msg = _make_message("s1", {"temp": 55})
    events = ef.process(msg)
    assert len(events) == 1
    assert events[0].label == "hot"
    assert events[0].kind == "rule"


def test_rule_event_does_not_fire_when_no_match() -> None:
    rules = [EventRuleConfig(sensor="s1", condition="temp > 50", priority="HIGH", label="hot")]
    ef = EventFilter(rules, [])
    msg = _make_message("s1", {"temp": 30})
    events = ef.process(msg)
    rule_events = [e for e in events if e.kind == "rule"]
    assert len(rule_events) == 0


def test_rule_event_only_fires_for_matching_sensor() -> None:
    rules = [EventRuleConfig(sensor="s1", condition="v > 0", priority="LOW", label="pos")]
    ef = EventFilter(rules, [])
    msg = _make_message("s2", {"v": 100})
    events = ef.process(msg)
    rule_events = [e for e in events if e.kind == "rule"]
    assert len(rule_events) == 0


# ── Anomaly detection tests ────────────────────────────────────


def test_anomaly_detection_triggers_on_spike() -> None:
    ef = EventFilter([], [], window_size=20, z_threshold=2.0)

    # Feed 10 stable readings with slight natural variance so pstdev > 0.
    for i in range(10):
        val = 10.0 + (i % 3) * 0.1  # 10.0, 10.1, 10.2, 10.0, ...
        msg = _make_message("s1", {"val": val}, ts=float(i))
        ef.process(msg)

    # Spike far outside normal range.
    msg = _make_message("s1", {"val": 100.0}, ts=11.0)
    events = ef.process(msg)
    anomaly_events = [e for e in events if e.kind == "anomaly"]
    assert len(anomaly_events) >= 1
    assert "val" in anomaly_events[0].label


def test_anomaly_detection_ignores_early_readings() -> None:
    """First 5 readings should never trigger anomaly (insufficient history)."""
    ef = EventFilter([], [], window_size=10, z_threshold=2.0)

    for i in range(4):
        msg = _make_message("s1", {"val": float(i * 100)}, ts=float(i))
        events = ef.process(msg)
        anomaly_events = [e for e in events if e.kind == "anomaly"]
        assert len(anomaly_events) == 0


# ── Summary window tests ───────────────────────────────────────


def test_summary_window_fires_at_interval() -> None:
    windows = [SummaryWindowConfig(sensors=["s1"], interval_seconds=5, label="status")]
    ef = EventFilter([], windows)

    # First message at ts=100 should trigger summary.
    # (last_seen defaults to 0.0, so 100.0 - 0.0 = 100 >= 5.)
    msg1 = _make_message("s1", {"v": 1, "semantic_summary": "test"}, ts=100.0)
    events1 = ef.process(msg1)
    summary_events = [e for e in events1 if e.kind == "summary"]
    assert len(summary_events) == 1

    # Message 2s later should NOT trigger summary.
    msg2 = _make_message("s1", {"v": 2, "semantic_summary": "test"}, ts=102.0)
    events2 = ef.process(msg2)
    summary_events = [e for e in events2 if e.kind == "summary"]
    assert len(summary_events) == 0

    # Message 6s after first summary should trigger again.
    msg3 = _make_message("s1", {"v": 3, "semantic_summary": "test"}, ts=106.0)
    events3 = ef.process(msg3)
    summary_events = [e for e in events3 if e.kind == "summary"]
    assert len(summary_events) == 1
