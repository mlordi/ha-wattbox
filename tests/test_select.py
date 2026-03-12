"""Test select platform for Wattbox integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.wattbox.select import WattboxOutletModeSelect, async_setup_entry


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Mock config entry for testing."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_entry_id"
    return config_entry


@pytest.fixture
def mock_coordinator() -> DataUpdateCoordinator:
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
            {"state": 1, "name": "Outlet 1", "mode": 0},
            {"state": 0, "name": "Outlet 2", "mode": 2},
            {"state": 1, "name": "Outlet 3", "mode": 1},
        ],
    }
    coordinator.async_set_outlet_mode = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test async_setup_entry for select platform."""
    hass.data["wattbox"] = {mock_config_entry.entry_id: mock_coordinator}
    entities_added = []

    async def mock_add_entities(entities):
        entities_added.extend(entities)

    result = await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    assert result is None
    assert len(entities_added) == 3
    assert all(isinstance(entity, WattboxOutletModeSelect) for entity in entities_added)


@pytest.mark.asyncio
async def test_async_setup_entry_default_outlets_sync_add(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test default outlet fallback path."""
    mock_coordinator.data = {"outlet_info": []}
    hass.data["wattbox"] = {mock_config_entry.entry_id: mock_coordinator}
    entities_added = []

    def mock_add_entities(entities):
        entities_added.extend(entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)
    assert len(entities_added) == 18


@pytest.mark.asyncio
async def test_async_setup_entry_with_none_add_entities(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test guard when add_entities callback is None."""
    hass.data["wattbox"] = {mock_config_entry.entry_id: MagicMock()}
    await async_setup_entry(hass, mock_config_entry, None)


@pytest.mark.asyncio
async def test_async_setup_entry_add_entities_exception(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Ensure add_entities exceptions are handled."""
    hass.data["wattbox"] = {mock_config_entry.entry_id: mock_coordinator}

    def bad_add_entities(_entities):
        raise RuntimeError("boom")

    await async_setup_entry(hass, mock_config_entry, bad_add_entities)


def test_mode_select_current_option(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test mode select current_option mapping."""
    select_1 = WattboxOutletModeSelect(mock_coordinator, {}, "test_mode_1", 1)
    select_2 = WattboxOutletModeSelect(mock_coordinator, {}, "test_mode_2", 2)
    select_3 = WattboxOutletModeSelect(mock_coordinator, {}, "test_mode_3", 3)

    assert select_1.current_option == "Enabled"
    assert select_2.current_option == "Reset Only"
    assert select_3.current_option == "Disabled"

    # Unknown mode falls back to Enabled
    mock_coordinator.data["outlet_info"][0]["mode"] = 99
    assert select_1.current_option == "Enabled"


def test_mode_select_name_and_none_current_option(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test name rendering and no-data current option."""
    select = WattboxOutletModeSelect(mock_coordinator, {}, "test_mode_1", 1)
    assert select.name == "Outlet 1 Mode"
    mock_coordinator.data = None
    assert select.current_option is None


@pytest.mark.asyncio
async def test_mode_select_set_option(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test mode select change dispatches to coordinator."""
    select = WattboxOutletModeSelect(mock_coordinator, {}, "test_mode_1", 1)

    await select.async_select_option("Reset Only")

    mock_coordinator.async_set_outlet_mode.assert_called_once_with(1, 2)


def test_select_inheritance(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test select inheritance."""
    select = WattboxOutletModeSelect(mock_coordinator, {}, "test_mode_1", 1)
    assert isinstance(select, SelectEntity)
