"""Test switch platform for Wattbox integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.wattbox.switch import (
    WattboxSwitch,
    async_setup_entry,
)


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Mock config entry for testing."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_entry_id"
    config_entry.data = {
        "host": "192.168.1.100",
        "username": "test_user",
        "password": "test_password",
        "polling_interval": 30,
    }
    config_entry.options = {}
    return config_entry


@pytest.fixture
def mock_coordinator(mock_config_entry: ConfigEntry) -> DataUpdateCoordinator:
    """Mock coordinator for testing."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.data = {
        "device_info": {
            "hardware_version": "1.0.0",
            "model": "WB-800VPS-IPVM-18",
            "serial_number": "TEST123",
            "hostname": "test-wattbox",
        },
        "outlet_info": [
            {"state": 1, "name": "Outlet 1"},
            {"state": 0, "name": "Outlet 2"},
            {"state": 1, "name": "Outlet 3"},
        ],
    }
    coordinator.async_set_outlet_state = AsyncMock()
    coordinator.config_entry = mock_config_entry
    return coordinator


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test async_setup_entry for switch platform."""
    # Ensure coordinator has outlet_info data
    mock_coordinator.data = {
        "device_info": {
            "hardware_version": "1.0.0",
            "model": "WB-800VPS-IPVM-18",
            "serial_number": "TEST123",
            "hostname": "test-wattbox",
        },
        "outlet_info": [
            {"state": 1, "name": "Outlet 1"},
            {"state": 0, "name": "Outlet 2"},
            {"state": 1, "name": "Outlet 3"},
        ],
    }

    # Mock the coordinator in hass.data
    hass.data["wattbox"] = {mock_config_entry.entry_id: mock_coordinator}

    # Create a mock async_add_entities function
    entities_added = []

    async def mock_add_entities(entities):
        entities_added.extend(entities)

    result = await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Should return None (no return value)
    assert result is None

    # Should have created 3 switches (one for each outlet in mock data)
    assert len(entities_added) == 3
    assert all(isinstance(entity, WattboxSwitch) for entity in entities_added)

    # Verify the switches have correct outlet numbers
    outlet_numbers = [entity._outlet_number for entity in entities_added]
    assert outlet_numbers == [1, 2, 3]


def test_wattbox_switch_init(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WattboxSwitch initialization."""
    switch = WattboxSwitch(
        coordinator=mock_coordinator,
        device_info={},
        unique_id="test_switch_1",
        outlet_number=1,
    )

    assert switch.coordinator == mock_coordinator
    assert switch.unique_id == "test_switch_1"
    assert switch.name == "01 Outlet 1"
    assert switch.device_class == "outlet"
    assert switch._outlet_number == 1


def test_wattbox_switch_is_on(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WattboxSwitch is_on property."""
    switch = WattboxSwitch(
        coordinator=mock_coordinator,
        device_info={},
        unique_id="test_switch_1",
        outlet_number=1,
    )

    # Test with outlet on
    assert switch.is_on is True

    # Test with outlet off
    switch._outlet_number = 2
    assert switch.is_on is False

    # Test with outlet on
    switch._outlet_number = 3
    assert switch.is_on is True

    # Test with no outlet data
    mock_coordinator.data = {"outlet_info": []}
    assert switch.is_on is None


@pytest.mark.asyncio
async def test_wattbox_switch_turn_on(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WattboxSwitch async_turn_on method."""
    switch = WattboxSwitch(
        coordinator=mock_coordinator,
        device_info={},
        unique_id="test_switch_1",
        outlet_number=1,
    )

    await switch.async_turn_on()

    # Should call coordinator's async_set_outlet_state with True
    mock_coordinator.async_set_outlet_state.assert_called_once_with(1, True)


@pytest.mark.asyncio
async def test_wattbox_switch_turn_off(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WattboxSwitch async_turn_off method."""
    switch = WattboxSwitch(
        coordinator=mock_coordinator,
        device_info={},
        unique_id="test_switch_1",
        outlet_number=1,
    )

    await switch.async_turn_off()

    # Should call coordinator's async_set_outlet_state with False
    mock_coordinator.async_set_outlet_state.assert_called_once_with(1, False)


def test_wattbox_switch_attributes(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WattboxSwitch attributes."""
    switch = WattboxSwitch(
        coordinator=mock_coordinator,
        device_info={},
        unique_id="test_switch_1",
        outlet_number=1,
    )

    assert switch.device_class == "outlet"
    assert switch.name == "01 Outlet 1"


def test_switch_inheritance(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test that switches inherit from correct base classes."""
    switch = WattboxSwitch(
        coordinator=mock_coordinator,
        device_info={},
        unique_id="test_switch_1",
        outlet_number=1,
    )

    assert isinstance(switch, SwitchEntity)


def test_switch_outlet_number_edge_cases(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test switch behavior with edge cases for outlet numbers."""
    # Test outlet number beyond available outlets
    switch = WattboxSwitch(
        coordinator=mock_coordinator,
        device_info={},
        unique_id="test_switch_10",
        outlet_number=10,  # Beyond the 3 outlets in mock data
    )

    # Should return None when outlet number is beyond available data
    assert switch.is_on is None


@pytest.mark.asyncio
async def test_switch_coordinator_integration(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test switch integration with coordinator."""
    switch = WattboxSwitch(
        coordinator=mock_coordinator,
        device_info={},
        unique_id="test_switch_1",
        outlet_number=1,
    )

    # Test turning on
    await switch.async_turn_on()
    mock_coordinator.async_set_outlet_state.assert_called_with(1, True)

    # Reset mock
    mock_coordinator.async_set_outlet_state.reset_mock()

    # Test turning off
    await switch.async_turn_off()
    mock_coordinator.async_set_outlet_state.assert_called_with(1, False)


@pytest.mark.asyncio
async def test_async_setup_entry_with_default_outlets_sync_add(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test default outlet fallback and sync add_entities path."""
    mock_coordinator.data = {"outlet_count": 2, "outlet_info": []}
    hass.data["wattbox"] = {mock_config_entry.entry_id: mock_coordinator}
    entities_added = []

    def mock_add_entities(entities):
        entities_added.extend(entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)
    assert len(entities_added) == 2


@pytest.mark.asyncio
async def test_async_setup_entry_with_none_add_entities(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test guard when add_entities callback is None."""
    hass.data["wattbox"] = {mock_config_entry.entry_id: MagicMock()}
    await async_setup_entry(hass, mock_config_entry, None)


def test_switch_name_fallback_without_options(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test name fallback when config option is missing."""
    mock_coordinator.config_entry.options = {}
    switch = WattboxSwitch(
        coordinator=mock_coordinator,
        device_info={},
        unique_id="test_switch_2",
        outlet_number=2,
    )
    assert switch.name == "02 Outlet 2"


def test_switch_available_false_when_not_enabled(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Switch should be unavailable for non-enabled mode."""
    mock_coordinator.data["outlet_info"][0]["mode"] = 2
    switch = WattboxSwitch(
        coordinator=mock_coordinator,
        device_info={},
        unique_id="test_switch_1",
        outlet_number=1,
    )
    assert switch.available is False


@pytest.mark.asyncio
async def test_switch_turn_on_off_raise_when_not_enabled(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Switch on/off should raise when outlet mode is not enabled."""
    mock_coordinator.data["outlet_info"][0]["mode"] = 1
    switch = WattboxSwitch(
        coordinator=mock_coordinator,
        device_info={},
        unique_id="test_switch_1",
        outlet_number=1,
    )

    with pytest.raises(HomeAssistantError):
        await switch.async_turn_on()
    with pytest.raises(HomeAssistantError):
        await switch.async_turn_off()
