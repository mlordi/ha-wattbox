"""Select platform for Wattbox integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import WattboxDataUpdateCoordinator
from .entity import WattboxOutletEntity

_LOGGER = logging.getLogger(__name__)

MODE_LABEL_TO_VALUE: dict[str, int] = {
    "Enabled": 0,
    "Disabled": 1,
    "Reset Only": 2,
}
MODE_VALUE_TO_LABEL: dict[int, str] = {value: key for key, value in MODE_LABEL_TO_VALUE.items()}


def _create_outlet_mode_selects(
    coordinator: WattboxDataUpdateCoordinator,
    config_entry: ConfigEntry,
    outlet_info: list,
) -> list["WattboxOutletModeSelect"]:
    """Create WattboxOutletModeSelect entities for outlets."""
    selects = []
    for i, _outlet in enumerate(outlet_info):
        select = WattboxOutletModeSelect(
            coordinator=coordinator,
            device_info=(
                coordinator.data.get("device_info", {}) if coordinator.data else {}
            ),
            unique_id=f"{config_entry.entry_id}_outlet_{i + 1}_mode",
            outlet_number=i + 1,
        )
        selects.append(select)
    return selects


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wattbox select entities."""
    if async_add_entities is None:
        _LOGGER.error(
            "CRITICAL: async_add_entities is None! This is a Home Assistant platform issue."
        )
        return

    coordinator: WattboxDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    outlet_info = coordinator.data.get("outlet_info", []) if coordinator.data else []
    if not outlet_info:
        outlet_info = [{"state": 0} for _ in range(18)]

    selects = _create_outlet_mode_selects(coordinator, config_entry, outlet_info)
    valid_selects = [select for select in selects if select is not None]

    if valid_selects:
        try:
            if asyncio.iscoroutinefunction(async_add_entities):
                await async_add_entities(valid_selects)
            else:
                async_add_entities(valid_selects)
        except Exception as e:
            _LOGGER.error("Error adding entities: %s", e)
            _LOGGER.error("async_add_entities type: %s", type(async_add_entities))
    else:
        _LOGGER.warning("No valid mode selects found for Wattbox integration")


class WattboxOutletModeSelect(WattboxOutletEntity, SelectEntity):
    """Representation of a Wattbox outlet mode select."""

    def __init__(
        self,
        coordinator: WattboxDataUpdateCoordinator,
        device_info: dict[str, Any],
        unique_id: str,
        outlet_number: int,
    ) -> None:
        """Initialize the outlet mode select."""
        super().__init__(coordinator, device_info, unique_id, outlet_number)
        self._attr_name = f"Outlet {outlet_number} Mode"
        self._attr_options = list(MODE_LABEL_TO_VALUE.keys())

    @property
    def current_option(self) -> str | None:
        """Return current outlet mode option."""
        if not self.coordinator.data:
            return None

        outlet_info = self.coordinator.data.get("outlet_info", [])
        if self._outlet_number <= len(outlet_info):
            outlet = outlet_info[self._outlet_number - 1]
            mode_value = outlet.get("mode", 0)
            return MODE_VALUE_TO_LABEL.get(mode_value, "Enabled")
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        mode_value = MODE_LABEL_TO_VALUE[option]
        await self.coordinator.async_set_outlet_mode(self._outlet_number, mode_value)
