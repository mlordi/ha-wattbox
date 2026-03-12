"""Button platform for Wattbox integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import WattboxDataUpdateCoordinator
from .entity import WattboxOutletEntity

_LOGGER = logging.getLogger(__name__)


def _outlet_mode(
    config_entry: ConfigEntry,
    outlet: dict[str, Any],
    outlet_number: int,
) -> int:
    """Resolve outlet mode from options first, then coordinator data."""
    return int(
        config_entry.options.get(
            f"outlet_{outlet_number}_mode",
            outlet.get("mode", 0),
        )
    )


def _create_outlet_reset_buttons(
    coordinator: WattboxDataUpdateCoordinator,
    config_entry: ConfigEntry,
    outlet_info: list,
) -> list["WattboxOutletResetButton"]:
    """Create reset button entities for outlets."""
    buttons = []
    for i, outlet in enumerate(outlet_info):
        outlet_number = i + 1
        if _outlet_mode(config_entry, outlet, outlet_number) == 1:
            continue
        button = WattboxOutletResetButton(
            coordinator=coordinator,
            device_info=(
                coordinator.data.get("device_info", {}) if coordinator.data else {}
            ),
            unique_id=f"{config_entry.entry_id}_outlet_{outlet_number}_reset",
            outlet_number=outlet_number,
        )
        buttons.append(button)
    return buttons


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wattbox button entities."""
    if async_add_entities is None:
        _LOGGER.error(
            "CRITICAL: async_add_entities is None! This is a Home Assistant platform issue."
        )
        return

    coordinator: WattboxDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    outlet_info = coordinator.data.get("outlet_info", []) if coordinator.data else []
    if not outlet_info:
        outlet_info = [{"state": 0} for _ in range(18)]

    buttons = _create_outlet_reset_buttons(coordinator, config_entry, outlet_info)
    valid_buttons = [button for button in buttons if button is not None]

    if valid_buttons:
        try:
            if asyncio.iscoroutinefunction(async_add_entities):
                await async_add_entities(valid_buttons)
            else:
                async_add_entities(valid_buttons)
        except Exception as e:
            _LOGGER.error("Error adding entities: %s", e)
            _LOGGER.error("async_add_entities type: %s", type(async_add_entities))
    else:
        _LOGGER.warning("No valid reset buttons found for Wattbox integration")


class WattboxOutletResetButton(WattboxOutletEntity, ButtonEntity):
    """Representation of a Wattbox outlet reset button."""

    def __init__(
        self,
        coordinator: WattboxDataUpdateCoordinator,
        device_info: dict[str, Any],
        unique_id: str,
        outlet_number: int,
    ) -> None:
        """Initialize the outlet reset button."""
        super().__init__(coordinator, device_info, unique_id, outlet_number)
        self._attr_name = f"Outlet {outlet_number} Reset"

    @property
    def name(self) -> str | None:
        """Return the name of the reset button."""
        prefix = f"{self._outlet_number:02d} "
        configured_name = self.coordinator.config_entry.options.get(
            f"outlet_{self._outlet_number}_name"
        )
        if configured_name:
            return f"{prefix}{configured_name} Reset"
        if not self.coordinator.data:
            return f"{prefix}{self._attr_name}"
        outlet_info = self.coordinator.data.get("outlet_info", [])
        if self._outlet_number <= len(outlet_info):
            outlet_name = outlet_info[self._outlet_number - 1].get(
                "name", f"Outlet {self._outlet_number}"
            )
            return f"{prefix}{outlet_name} Reset"
        return f"{prefix}{self._attr_name}"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_reset_outlet(self._outlet_number)
