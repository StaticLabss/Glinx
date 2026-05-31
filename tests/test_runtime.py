from glinx.config import GlinxConfig
from glinx.runtime import GlinxRuntime


def test_runtime_generates_tool_specs() -> None:
    config = GlinxConfig.model_validate(
        {
            "ingestion": {
                "sources": [
                    {
                        "id": "left_fingertip",
                        "protocol": "mock",
                        "payloads": [{"p": 23.4, "temp": 31.1}],
                    }
                ]
            },
            "sensors": [
                {
                    "id": "left_fingertip",
                    "type": "force_sensor",
                    "location": "robot.hand.left.fingertip",
                    "unit": "kPa",
                    "fields": {"p": "contact_pressure", "temp": "surface_temperature"},
                }
            ],
        }
    )
    runtime = GlinxRuntime(config)

    import asyncio

    asyncio.run(runtime.poll_once())

    specs = runtime.tool_specs()
    assert any(spec["name"] == "get_left_fingertip_status" for spec in specs)


def test_rule_event_uses_enriched_fields() -> None:
    config = GlinxConfig.model_validate(
        {
            "ingestion": {
                "sources": [
                    {
                        "id": "left_fingertip",
                        "protocol": "mock",
                        "payloads": [{"p": 58.4, "temp": 31.5}],
                    }
                ]
            },
            "sensors": [
                {
                    "id": "left_fingertip",
                    "type": "force_sensor",
                    "location": "robot.hand.left.fingertip",
                    "unit": "kPa",
                    "fields": {"p": "contact_pressure", "temp": "surface_temperature"},
                }
            ],
            "event_rules": [
                {
                    "sensor": "left_fingertip",
                    "condition": "contact_pressure_kPa > 50",
                    "priority": "HIGH",
                    "label": "grip_overload",
                }
            ],
        }
    )
    runtime = GlinxRuntime(config)

    import asyncio

    asyncio.run(runtime.poll_once())

    assert runtime.events
    assert runtime.events[0].label == "grip_overload"
