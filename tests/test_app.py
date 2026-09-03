"""Tests for the decorator-based Glinx app API."""

from glinx.app import Glinx


def test_sensor_registration() -> None:
    """Decorating a function with @app.sensor registers it internally."""
    app = Glinx(name="test")

    @app.sensor("temp", protocol="mock", payloads=[{"t": 22.5}])
    def temp(raw):
        return {"temperature": raw["t"]}

    assert len(app._sensors) == 1
    assert app._sensors[0].id == "temp"
    assert app._sensors[0].protocol == "mock"
    assert app._transforms["temp"] is temp


def test_rule_registration() -> None:
    """Decorating with @app.rule registers an event rule config."""
    app = Glinx()

    @app.sensor("s1", protocol="mock", payloads=[{"v": 10}])
    def s1(raw):
        return raw

    @app.rule("s1", when="v > 5", priority="HIGH")
    def high_value(event):
        pass

    assert len(app._rules) == 1
    assert app._rules[0].condition == "v > 5"
    assert app._rules[0].label == "high_value"
    assert app._rules[0].priority == "HIGH"


def test_summary_registration() -> None:
    """Decorating with @app.summary registers a summary window."""
    app = Glinx()

    @app.sensor("s1", protocol="mock", payloads=[{"v": 1}])
    def s1(raw):
        return raw

    @app.summary(["s1"], interval_seconds=10, label="status")
    def periodic(event):
        pass

    assert len(app._summaries) == 1
    assert app._summaries[0].sensors == ["s1"]
    assert app._summaries[0].interval_seconds == 10


def test_on_event_registration() -> None:
    """on_event registers a callback for a given label."""
    app = Glinx()

    @app.on_event("overheat")
    def handle(event):
        pass

    assert "overheat" in app._event_callbacks
    assert app._event_callbacks["overheat"] is handle


def test_build_config_produces_valid_config() -> None:
    """_build_config compiles registrations into a GlinxConfig."""
    app = Glinx(name="robot")

    @app.sensor(
        "imu",
        protocol="mock",
        payloads=[{"ax": 0.1}],
        fields={"ax": "accel_x"},
        sensor_type="imu",
        location="robot.base",
    )
    def imu(raw):
        return raw

    @app.rule("imu", when="accel_x > 10", priority="HIGH", label="shock")
    def shock(event):
        pass

    config = app._build_config()

    assert config.glinx.name == "robot"
    assert len(config.ingestion.sources) == 1
    assert config.ingestion.sources[0].id == "imu"
    assert config.ingestion.sources[0].protocol == "mock"
    assert len(config.sensors) == 1
    assert config.sensors[0].fields == {"ax": "accel_x"}
    assert len(config.event_rules) == 1
    assert config.event_rules[0].label == "shock"


def test_poll_once_with_mock() -> None:
    """poll_once should run one ingestion cycle and return results."""
    app = Glinx()

    @app.sensor("s1", protocol="mock", payloads=[{"x": 42}])
    def s1(raw):
        return raw

    results = app.poll_once()
    assert "s1" in results
    assert len(results["s1"]) == 1
    assert results["s1"][0].parsed == {"x": 42}


def test_sensor_transform_is_applied_to_agent_data() -> None:
    app = Glinx()

    @app.sensor("room", protocol="mock", payloads=[{"t": 22.5}])
    def room(raw):
        return {"temperature_c": raw["t"]}

    message = app.poll_once()["room"][0]

    assert message.parsed == {"temperature_c": 22.5}
    assert message.enriched == {"temperature_c": 22.5}
    assert app._runtime is not None
    assert "temperature_c" in app._runtime.snapshots["room"].output_schema["properties"]


def test_repr() -> None:
    app = Glinx(name="demo")

    @app.sensor("a", protocol="mock", payloads=[{"v": 1}])
    def a(raw):
        return raw

    @app.rule("a", when="v > 0")
    def r(event):
        pass

    assert "demo" in repr(app)
    assert "sensors=1" in repr(app)
    assert "rules=1" in repr(app)
