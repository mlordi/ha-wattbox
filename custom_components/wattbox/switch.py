"""Switch platform for Wattbox integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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


def _create_outlet_switches(
    coordinator: WattboxDataUpdateCoordinator,
    config_entry: ConfigEntry,
    outlet_info: list,
) -> list[WattboxSwitch]:
    """Create WattboxSwitch instances for outlets."""
    switches = []
    for i, outlet in enumerate(outlet_info):
        outlet_number = i + 1
        if _outlet_mode(config_entry, outlet, outlet_number) != 0:
            continue
        switch = WattboxSwitch(
            coordinator=coordinator,
            device_info=(
                coordinator.data.get("device_info", {}) if coordinator.data else {}
            ),
            unique_id=f"{config_entry.entry_id}_outlet_{outlet_number}",
            outlet_number=outlet_number,
        )
        switches.append(switch)
    return switches


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wattbox switch entities."""
    # Check if async_add_entities is None
    if async_add_entities is None:
        _LOGGER.error(
            "CRITICAL: async_add_entities is None! This is a Home Assistant platform issue."
        )
        return

    coordinator: WattboxDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Get outlet info from coordinator data - handle missing data gracefully
    outlet_info = coordinator.data.get("outlet_info", []) if coordinator.data else []

    # Ensure outlet_info is a list and not None
    if outlet_info is None:
        outlet_info = []

    # If no outlet data is available yet, create a default set of switches
    # This ensures entities are created even before first data fetch
    if not outlet_info:
        _LOGGER.info("No outlet data available yet, creating default switches")
        outlet_count = (
            coordinator.data.get("outlet_count", 12) if coordinator.data else 12
        )
        outlet_info = [{"state": 0} for _ in range(outlet_count)]

    # Create switches for each outlet
    switches = _create_outlet_switches(coordinator, config_entry, outlet_info)

    # Filter out any None switches and add only valid ones
    valid_switches = [switch for switch in switches if switch is not None]

    if valid_switches:
        # Try calling without await first, as it might not be async
        try:
            if asyncio.iscoroutinefunction(async_add_entities):
                await async_add_entities(valid_switches)
            else:
                async_add_entities(valid_switches)
        except Exception as e:
            _LOGGER.error(f"Error adding entities: {e}")
            _LOGGER.error(f"async_add_entities type: {type(async_add_entities)}")
    else:
        _LOGGER.warning("No valid switches found for Wattbox integration")


class WattboxSwitch(WattboxOutletEntity, SwitchEntity):
    """Representation of a Wattbox outlet switch."""

    def __init__(
        self,
        coordinator: WattboxDataUpdateCoordinator,
        device_info: dict[str, Any],
        unique_id: str,
        outlet_number: int,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_info, unique_id, outlet_number)
        self._attr_name = f"Outlet {outlet_number}"
        self._attr_device_class = "outlet"

    @property
    def name(self) -> str | None:
        """Return the name of the switch."""
        prefix = f"{self._outlet_number:02d} "
        configured_name = self.coordinator.config_entry.options.get(
            f"outlet_{self._outlet_number}_name"
        )
        if configured_name:
            return f"{prefix}{configured_name}"
        if not self.coordinator.data:
            return f"{prefix}{self._attr_name}"
        outlet_info = self.coordinator.data.get("outlet_info", [])
        if self._outlet_number <= len(outlet_info):
            outlet_name = outlet_info[self._outlet_number - 1].get(
                "name", f"Outlet {self._outlet_number}"
            )
            return f"{prefix}{outlet_name}"
        return f"{prefix}{self._attr_name}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if not self.coordinator.data:
            return None
        outlet_info = self.coordinator.data.get("outlet_info", [])
        if self._outlet_number <= len(outlet_info):
            outlet = outlet_info[self._outlet_number - 1]
            return bool(outlet.get("state", 0))
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False
        if not self.coordinator.data:
            return True
        outlet_info = self.coordinator.data.get("outlet_info", [])
        if self._outlet_number <= len(outlet_info):
            # Reset Only mode does not support ON/OFF operations.
            mode = _outlet_mode(
                self.coordinator.config_entry,
                outlet_info[self._outlet_number - 1],
                self._outlet_number,
            )
            return mode == 0
        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        outlet_info = (
            self.coordinator.data.get("outlet_info", [])
            if self.coordinator.data
            else []
        )
        if self._outlet_number <= len(outlet_info):
            mode = _outlet_mode(
                self.coordinator.config_entry,
                outlet_info[self._outlet_number - 1],
                self._outlet_number,
            )
            if mode != 0:
                raise HomeAssistantError(
                    "Outlet is not in Enabled mode. Use integration Configure to change mode."
                )
        await self.coordinator.async_set_outlet_state(self._outlet_number, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        outlet_info = (
            self.coordinator.data.get("outlet_info", [])
            if self.coordinator.data
            else []
        )
        if self._outlet_number <= len(outlet_info):
            mode = _outlet_mode(
                self.coordinator.config_entry,
                outlet_info[self._outlet_number - 1],
                self._outlet_number,
            )
            if mode != 0:
                raise HomeAssistantError(
                    "Outlet is not in Enabled mode. Use integration Configure to change mode."
                )
        await self.coordinator.async_set_outlet_state(self._outlet_number, False)
