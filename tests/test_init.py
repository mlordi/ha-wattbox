"""Test the Wattbox integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.wattbox import async_setup_entry, async_unload_entry
from custom_components.wattbox.const import (
    DOMAIN,
    SERVICE_RESET_OUTLET,
    SERVICE_SET_OUTLET_MODE,
    SERVICE_SET_OUTLET_STATE,
    SERVICE_TOGGLE_OUTLET,
)


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Mock config entry for testing."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.version = 1
    config_entry.domain = DOMAIN
    config_entry.title = "Test Wattbox"
    config_entry.data = {
        "host": "192.168.1.100",
        "username": "wattbox",
        "password": "wattbox",
        "polling_interval": 30,
    }
    config_entry.source = "user"
    config_entry.options = {}
    config_entry.entry_id = "test_entry_id"
    return config_entry


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test async_setup_entry."""
    with (
        patch(
            "custom_components.wattbox.coordinator.WattboxDataUpdateCoordinator.async_config_entry_first_refresh",
            new_callable=AsyncMock,
        ),
        patch("homeassistant.helpers.frame.report_usage"),
    ):
        result = await async_setup_entry(hass, mock_config_entry)

    assert result is True
    assert DOMAIN in hass.data


@pytest.mark.asyncio
async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test async_unload_entry."""
    # First set up the entry
    with (
        patch(
            "custom_components.wattbox.coordinator.WattboxDataUpdateCoordinator.async_config_entry_first_refresh",
            new_callable=AsyncMock,
        ),
        patch("homeassistant.helpers.frame.report_usage"),
    ):
        await async_setup_entry(hass, mock_config_entry)

    # Then unload it
    result = await async_unload_entry(hass, mock_config_entry)

    assert result is True


@pytest.mark.asyncio
async def test_async_setup_entry_with_existing_data(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test async_setup_entry when data already exists."""
    # Pre-populate hass.data
    hass.data[DOMAIN] = {"existing": "data"}

    with (
        patch(
            "custom_components.wattbox.coordinator.WattboxDataUpdateCoordinator.async_config_entry_first_refresh",
            new_callable=AsyncMock,
        ),
        patch("homeassistant.helpers.frame.report_usage"),
    ):
        result = await async_setup_entry(hass, mock_config_entry)

    assert result is True
    assert DOMAIN in hass.data
    # Should preserve existing data
    assert "existing" in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_async_setup_entry_platforms_disabled(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test async_setup_entry when platforms are disabled (TODO sections)."""
    # The current implementation has TODO sections for platform setup
    # This test verifies it doesn't crash
    with (
        patch(
            "custom_components.wattbox.coordinator.WattboxDataUpdateCoordinator.async_config_entry_first_refresh",
            new_callable=AsyncMock,
        ),
        patch("homeassistant.helpers.frame.report_usage"),
    ):
        result = await async_setup_entry(hass, mock_config_entry)

    assert result is True


@pytest.mark.asyncio
async def test_async_unload_entry_platforms_disabled(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test async_unload_entry when platforms are disabled (TODO sections)."""
    # Set up the data first
    mock_coordinator = MagicMock()
    mock_coordinator.async_disconnect = AsyncMock()
    hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_coordinator}

    # The current implementation has TODO sections for platform unload
    # This test verifies it doesn't crash
    result = await async_unload_entry(hass, mock_config_entry)

    assert result is True


@pytest.mark.asyncio
async def test_services_are_registered(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test service registration during setup."""
    with (
        patch(
            "custom_components.wattbox.coordinator.WattboxDataUpdateCoordinator.async_config_entry_first_refresh",
            new_callable=AsyncMock,
        ),
        patch("homeassistant.helpers.frame.report_usage"),
    ):
        await async_setup_entry(hass, mock_config_entry)

    service_names = [
        call.args[1] for call in hass.services.async_register.call_args_list
    ]
    assert SERVICE_SET_OUTLET_MODE in service_names
    assert SERVICE_SET_OUTLET_STATE in service_names
    assert SERVICE_TOGGLE_OUTLET in service_names
    assert SERVICE_RESET_OUTLET in service_names


@pytest.mark.asyncio
async def test_set_outlet_state_service_handler(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test set_outlet_state service execution."""
    with (
        patch(
            "custom_components.wattbox.coordinator.WattboxDataUpdateCoordinator.async_config_entry_first_refresh",
            new_callable=AsyncMock,
        ),
        patch("homeassistant.helpers.frame.report_usage"),
    ):
        await async_setup_entry(hass, mock_config_entry)

    fake_coordinator = MagicMock()
    fake_coordinator.data = {"outlet_info": [{"state": 1, "mode": 0}]}
    fake_coordinator.config_entry = mock_config_entry
    fake_coordinator.async_set_outlet_state = AsyncMock()
    fake_coordinator.async_reset_outlet = AsyncMock()
    fake_coordinator.async_set_outlet_mode = AsyncMock()
    hass.data[DOMAIN][mock_config_entry.entry_id] = fake_coordinator

    handlers = {
        call.args[1]: call.args[2]
        for call in hass.services.async_register.call_args_list
    }
    handler = handlers[SERVICE_SET_OUTLET_STATE]

    await handler(
        ServiceCall(
            {
                "entry_id": mock_config_entry.entry_id,
                "outlet_number": 1,
                "state": True,
            }
        )
    )
    fake_coordinator.async_set_outlet_state.assert_called_once_with(1, True)


@pytest.mark.asyncio
async def test_unload_removes_services_when_last_entry(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test service cleanup when unloading final config entry."""
    with (
        patch(
            "custom_components.wattbox.coordinator.WattboxDataUpdateCoordinator.async_config_entry_first_refresh",
            new_callable=AsyncMock,
        ),
        patch("homeassistant.helpers.frame.report_usage"),
    ):
        await async_setup_entry(hass, mock_config_entry)

    await async_unload_entry(hass, mock_config_entry)

    removed = [call.args[1] for call in hass.services.async_remove.call_args_list]
    assert SERVICE_SET_OUTLET_MODE in removed
    assert SERVICE_SET_OUTLET_STATE in removed
    assert SERVICE_TOGGLE_OUTLET in removed
    assert SERVICE_RESET_OUTLET in removed


@pytest.mark.asyncio
async def test_service_handlers_reject_invalid_mode_actions(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test mode guardrails in service handlers."""
    with (
        patch(
            "custom_components.wattbox.coordinator.WattboxDataUpdateCoordinator.async_config_entry_first_refresh",
            new_callable=AsyncMock,
        ),
        patch("homeassistant.helpers.frame.report_usage"),
    ):
        await async_setup_entry(hass, mock_config_entry)

    fake_coordinator = MagicMock()
    fake_coordinator.data = {"outlet_info": [{"state": 1, "mode": 1}]}
    fake_coordinator.config_entry = mock_config_entry
    fake_coordinator.async_set_outlet_state = AsyncMock()
    fake_coordinator.async_reset_outlet = AsyncMock()
    fake_coordinator.async_set_outlet_mode = AsyncMock()
    hass.data[DOMAIN][mock_config_entry.entry_id] = fake_coordinator

    handlers = {
        call.args[1]: call.args[2]
        for call in hass.services.async_register.call_args_list
    }

    with pytest.raises(HomeAssistantError):
        await handlers[SERVICE_SET_OUTLET_STATE](
            ServiceCall(
                {
                    "entry_id": mock_config_entry.entry_id,
                    "outlet_number": 1,
                    "state": False,
                }
            )
        )

    with pytest.raises(HomeAssistantError):
        await handlers[SERVICE_TOGGLE_OUTLET](
            ServiceCall({"entry_id": mock_config_entry.entry_id, "outlet_number": 1})
        )

    with pytest.raises(HomeAssistantError):
        await handlers[SERVICE_RESET_OUTLET](
            ServiceCall({"entry_id": mock_config_entry.entry_id, "outlet_number": 1})
        )


@pytest.mark.asyncio
async def test_toggle_and_mode_services_execute(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test toggle and mode service happy paths."""
    with (
        patch(
            "custom_components.wattbox.coordinator.WattboxDataUpdateCoordinator.async_config_entry_first_refresh",
            new_callable=AsyncMock,
        ),
        patch("homeassistant.helpers.frame.report_usage"),
    ):
        await async_setup_entry(hass, mock_config_entry)

    fake_coordinator = MagicMock()
    fake_coordinator.data = {"outlet_info": [{"state": 0, "mode": 0}]}
    fake_coordinator.config_entry = mock_config_entry
    fake_coordinator.async_set_outlet_state = AsyncMock()
    fake_coordinator.async_reset_outlet = AsyncMock()
    fake_coordinator.async_set_outlet_mode = AsyncMock()
    hass.data[DOMAIN][mock_config_entry.entry_id] = fake_coordinator

    handlers = {
        call.args[1]: call.args[2]
        for call in hass.services.async_register.call_args_list
    }

    await handlers[SERVICE_TOGGLE_OUTLET](
        ServiceCall({"entry_id": mock_config_entry.entry_id, "outlet_number": 1})
    )
    fake_coordinator.async_set_outlet_state.assert_called_with(1, True)

    await handlers[SERVICE_SET_OUTLET_MODE](
        ServiceCall(
            {"entry_id": mock_config_entry.entry_id, "outlet_number": 1, "mode": 2}
        )
    )
    fake_coordinator.async_set_outlet_mode.assert_called_with(1, 2)
    hass.config_entries.async_reload.assert_called_with(mock_config_entry.entry_id)
