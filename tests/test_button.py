"""Test button platform for Wattbox integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.wattbox.button import WattboxOutletResetButton, async_setup_entry


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Mock config entry for testing."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_entry_id"
    config_entry.options = {}
    return config_entry


@pytest.fixture
def mock_coordinator(mock_config_entry: ConfigEntry) -> DataUpdateCoordinator:
    """Mock coordinator for testing."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.config_entry = mock_config_entry
    coordinator.data = {
        "device_info": {"serial_number": "TEST123", "hostname": "test-wattbox"},
        "outlet_info": [
            {"state": 1, "name": "Outlet 1", "mode": 0},
            {"state": 0, "name": "Outlet 2", "mode": 1},
            {"state": 1, "name": "Outlet 3", "mode": 2},
        ],
    }
    coordinator.async_reset_outlet = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_async_setup_entry_filters_disabled_mode(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Mode 1 outlet should not get a reset button."""
    hass.data["wattbox"] = {mock_config_entry.entry_id: mock_coordinator}
    entities_added = []

    async def mock_add_entities(entities):
        entities_added.extend(entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    assert len(entities_added) == 2
    assert [entity._outlet_number for entity in entities_added] == [1, 3]


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


def test_button_name_uses_configured_name(
    mock_coordinator: DataUpdateCoordinator, mock_config_entry: ConfigEntry
) -> None:
    """Button name should prefer configured outlet name."""
    mock_config_entry.options["outlet_1_name"] = "Rack Core"
    button = WattboxOutletResetButton(mock_coordinator, {}, "uid", 1)
    assert button.name == "01 Rack Core Reset"


def test_button_name_fallback_paths(
    mock_coordinator: DataUpdateCoordinator, mock_config_entry: ConfigEntry
) -> None:
    """Test fallback name construction for button."""
    mock_config_entry.options = {}
    button = WattboxOutletResetButton(mock_coordinator, {}, "uid", 3)
    assert button.name == "03 Outlet 3 Reset"

    mock_coordinator.data = {}
    assert button.name == "03 Outlet 3 Reset"


@pytest.mark.asyncio
async def test_button_press_calls_coordinator(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Button press triggers outlet reset."""
    button = WattboxOutletResetButton(mock_coordinator, {}, "uid", 3)
    await button.async_press()
    mock_coordinator.async_reset_outlet.assert_called_once_with(3)


def test_button_inheritance(mock_coordinator: DataUpdateCoordinator) -> None:
    """Buttons should derive from ButtonEntity."""
    button = WattboxOutletResetButton(mock_coordinator, {}, "uid", 1)
    assert isinstance(button, ButtonEntity)
