"""The Wattbox integration for Home Assistant."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    OUTLET_MODE_DISABLED,
    OUTLET_MODE_ENABLED,
    OUTLET_MODE_RESET_ONLY,
    SERVICE_ATTR_ENTRY_ID,
    SERVICE_ATTR_MODE,
    SERVICE_ATTR_OUTLET_NUMBER,
    SERVICE_ATTR_STATE,
    SERVICE_RESET_OUTLET,
    SERVICE_SET_OUTLET_MODE,
    SERVICE_SET_OUTLET_STATE,
    SERVICE_TOGGLE_OUTLET,
)
from .coordinator import WattboxDataUpdateCoordinator
from .telnet_client import WattboxTelnetClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


def _build_initial_outlet_options(
    entry: ConfigEntry,
    outlet_info: list[dict],
) -> dict:
    """Build initial options from detected outlet data."""
    options = dict(entry.options)
    changed = False

    detected_count = len(outlet_info)
    if options.get("outlet_count") != detected_count:
        options["outlet_count"] = detected_count
        changed = True

    for i, outlet in enumerate(outlet_info, start=1):
        name_key = f"outlet_{i}_name"
        mode_key = f"outlet_{i}_mode"

        detected_name = outlet.get("name", f"Outlet {i}")
        detected_mode = int(outlet.get("mode", 0))

        if name_key not in options and detected_name:
            options[name_key] = detected_name
            changed = True
        if mode_key not in options:
            options[mode_key] = detected_mode
            changed = True

    return options if changed else {}


def _stale_unique_ids_for_entry(
    entry: ConfigEntry,
    outlet_info: list[dict],
) -> set[str]:
    """Build list of stale unique_ids to remove from entity registry."""
    stale_unique_ids: set[str] = set()
    entry_id = entry.entry_id

    # Remove all old mode select entities (mode is now configured in Options Flow).
    for i in range(1, len(outlet_info) + 1):
        stale_unique_ids.add(f"{entry_id}_outlet_{i}_mode")

    # Keep entity set aligned to outlet mode:
    # mode 0: switch + reset button, no always-on status
    # mode 1: no switch/button, show always-on status
    # mode 2: no switch, show reset button, no always-on status
    for i, outlet in enumerate(outlet_info, start=1):
        mode = int(entry.options.get(f"outlet_{i}_mode", outlet.get("mode", 0)))
        if mode in (1, 2):
            stale_unique_ids.add(f"{entry_id}_outlet_{i}")
        if mode == 1:
            stale_unique_ids.add(f"{entry_id}_outlet_{i}_reset")
        if mode in (0, 2):
            stale_unique_ids.add(f"{entry_id}_outlet_{i}_always_on")

    return stale_unique_ids


def _cleanup_stale_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    outlet_info: list[dict],
) -> None:
    """Remove stale entities from HA entity registry."""
    entity_registry = er.async_get(hass)
    stale_unique_ids = _stale_unique_ids_for_entry(entry, outlet_info)
    if not stale_unique_ids:
        return

    for entity_entry in list(entity_registry.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id:
            continue
        if entity_entry.unique_id in stale_unique_ids:
            entity_registry.async_remove(entity_entry.entity_id)


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up Wattbox from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create telnet client
    telnet_client = WattboxTelnetClient(
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    # Create coordinator
    coordinator = WattboxDataUpdateCoordinator(hass, entry, telnet_client)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    outlet_info = coordinator.data.get("outlet_info", []) if coordinator.data else []

    initial_options = _build_initial_outlet_options(entry, outlet_info)
    if initial_options:
        hass.config_entries.async_update_entry(entry, options=initial_options)

    _cleanup_stale_entities(hass, entry, outlet_info)

    if not hass.services.has_service(DOMAIN, SERVICE_SET_OUTLET_MODE):
        service_schema = vol.Schema(
            {
                vol.Required(SERVICE_ATTR_ENTRY_ID): str,
                vol.Required(SERVICE_ATTR_OUTLET_NUMBER): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
                vol.Required(SERVICE_ATTR_MODE): vol.In(
                    [OUTLET_MODE_ENABLED, OUTLET_MODE_DISABLED, OUTLET_MODE_RESET_ONLY]
                ),
            }
        )

        async def handle_set_outlet_mode(call: ServiceCall) -> None:
            entry_id = call.data[SERVICE_ATTR_ENTRY_ID]
            outlet_number = call.data[SERVICE_ATTR_OUTLET_NUMBER]
            mode = call.data[SERVICE_ATTR_MODE]

            coordinator_for_entry = hass.data[DOMAIN].get(entry_id)
            if coordinator_for_entry is None:
                raise HomeAssistantError(
                    f"Unknown Wattbox entry_id '{entry_id}' for service call"
                )

            await coordinator_for_entry.async_set_outlet_mode(outlet_number, mode)
            await hass.config_entries.async_reload(entry_id)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_OUTLET_MODE,
            handle_set_outlet_mode,
            schema=service_schema,
        )

    def _get_outlet_mode(
        coordinator_for_entry: WattboxDataUpdateCoordinator, outlet_number: int
    ) -> int:
        outlet_info = (
            coordinator_for_entry.data.get("outlet_info", [])
            if coordinator_for_entry.data
            else []
        )
        outlet = (
            outlet_info[outlet_number - 1]
            if 1 <= outlet_number <= len(outlet_info)
            else {}
        )
        return int(
            coordinator_for_entry.config_entry.options.get(
                f"outlet_{outlet_number}_mode",
                outlet.get("mode", 0),
            )
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_OUTLET_STATE):
        state_schema = vol.Schema(
            {
                vol.Required(SERVICE_ATTR_ENTRY_ID): str,
                vol.Required(SERVICE_ATTR_OUTLET_NUMBER): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
                vol.Required(SERVICE_ATTR_STATE): bool,
            }
        )

        async def handle_set_outlet_state(call: ServiceCall) -> None:
            entry_id = call.data[SERVICE_ATTR_ENTRY_ID]
            outlet_number = call.data[SERVICE_ATTR_OUTLET_NUMBER]
            state = call.data[SERVICE_ATTR_STATE]

            coordinator_for_entry = hass.data[DOMAIN].get(entry_id)
            if coordinator_for_entry is None:
                raise HomeAssistantError(
                    f"Unknown Wattbox entry_id '{entry_id}' for service call"
                )

            if _get_outlet_mode(coordinator_for_entry, outlet_number) != 0:
                raise HomeAssistantError(
                    "Outlet is not in Enabled mode; cannot set ON/OFF state."
                )

            await coordinator_for_entry.async_set_outlet_state(outlet_number, state)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_OUTLET_STATE,
            handle_set_outlet_state,
            schema=state_schema,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_TOGGLE_OUTLET):
        toggle_schema = vol.Schema(
            {
                vol.Required(SERVICE_ATTR_ENTRY_ID): str,
                vol.Required(SERVICE_ATTR_OUTLET_NUMBER): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
            }
        )

        async def handle_toggle_outlet(call: ServiceCall) -> None:
            entry_id = call.data[SERVICE_ATTR_ENTRY_ID]
            outlet_number = call.data[SERVICE_ATTR_OUTLET_NUMBER]

            coordinator_for_entry = hass.data[DOMAIN].get(entry_id)
            if coordinator_for_entry is None:
                raise HomeAssistantError(
                    f"Unknown Wattbox entry_id '{entry_id}' for service call"
                )

            if _get_outlet_mode(coordinator_for_entry, outlet_number) != 0:
                raise HomeAssistantError(
                    "Outlet is not in Enabled mode; cannot toggle state."
                )

            outlet_info = (
                coordinator_for_entry.data.get("outlet_info", [])
                if coordinator_for_entry.data
                else []
            )
            current_is_on = False
            if 1 <= outlet_number <= len(outlet_info):
                current_is_on = bool(outlet_info[outlet_number - 1].get("state", 0))

            await coordinator_for_entry.async_set_outlet_state(
                outlet_number, not current_is_on
            )

        hass.services.async_register(
            DOMAIN,
            SERVICE_TOGGLE_OUTLET,
            handle_toggle_outlet,
            schema=toggle_schema,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_RESET_OUTLET):
        reset_schema = vol.Schema(
            {
                vol.Required(SERVICE_ATTR_ENTRY_ID): str,
                vol.Required(SERVICE_ATTR_OUTLET_NUMBER): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
            }
        )

        async def handle_reset_outlet(call: ServiceCall) -> None:
            entry_id = call.data[SERVICE_ATTR_ENTRY_ID]
            outlet_number = call.data[SERVICE_ATTR_OUTLET_NUMBER]

            coordinator_for_entry = hass.data[DOMAIN].get(entry_id)
            if coordinator_for_entry is None:
                raise HomeAssistantError(
                    f"Unknown Wattbox entry_id '{entry_id}' for service call"
                )

            if _get_outlet_mode(coordinator_for_entry, outlet_number) == 1:
                raise HomeAssistantError(
                    "Outlet is in Disabled mode; reset action is not available."
                )

            await coordinator_for_entry.async_reset_outlet(outlet_number)

        hass.services.async_register(
            DOMAIN,
            SERVICE_RESET_OUTLET,
            handle_reset_outlet,
            schema=reset_schema,
        )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Disconnect from device
    if entry.entry_id in hass.data[DOMAIN]:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_disconnect()
        del hass.data[DOMAIN][entry.entry_id]

    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_SET_OUTLET_MODE)
        hass.services.async_remove(DOMAIN, SERVICE_SET_OUTLET_STATE)
        hass.services.async_remove(DOMAIN, SERVICE_TOGGLE_OUTLET)
        hass.services.async_remove(DOMAIN, SERVICE_RESET_OUTLET)

    return unload_ok
