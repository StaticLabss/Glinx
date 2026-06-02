"""Tests for protocol drivers."""

import pytest

from glinx.config import SourceConfig
from glinx.drivers.base import DriverRegistry
from glinx.drivers.mock import MockDriver


# ── MockDriver tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_mock_driver_returns_payload() -> None:
    source = SourceConfig.model_validate(
        {"id": "s1", "protocol": "mock", "payloads": [{"x": 1}, {"x": 2}]}
    )
    driver = MockDriver(source)
    msgs = await driver.poll()
    assert len(msgs) == 1
    assert msgs[0].parsed == {"x": 1}

    msgs2 = await driver.poll()
    assert msgs2[0].parsed == {"x": 2}

    # Wraps around.
    msgs3 = await driver.poll()
    assert msgs3[0].parsed == {"x": 1}


@pytest.mark.asyncio
async def test_mock_driver_empty_payloads() -> None:
    source = SourceConfig.model_validate(
        {"id": "s1", "protocol": "mock", "payloads": []}
    )
    driver = MockDriver(source)
    msgs = await driver.poll()
    assert msgs == []


# ── DriverRegistry tests ──────────────────────────────────────


def test_registry_create_known_protocol() -> None:
    registry = DriverRegistry()
    registry.register("mock", MockDriver)
    source = SourceConfig.model_validate(
        {"id": "s1", "protocol": "mock", "payloads": [{"v": 1}]}
    )
    driver = registry.create(source)
    assert isinstance(driver, MockDriver)


def test_registry_create_unknown_protocol_raises() -> None:
    registry = DriverRegistry()
    source = SourceConfig.model_validate(
        {"id": "s1", "protocol": "unknown_proto"}
    )
    with pytest.raises(ValueError, match="No driver registered"):
        registry.create(source)


def test_registry_protocols_returns_sorted() -> None:
    registry = DriverRegistry()
    registry.register("z_proto", MockDriver)
    registry.register("a_proto", MockDriver)
    assert registry.protocols() == ["a_proto", "z_proto"]
