"""Config flow for Wattbox integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_POLLING_INTERVAL,
    DEFAULT_PASSWORD,
    DEFAULT_POLLING_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
        vol.Optional(CONF_POLLING_INTERVAL, default=DEFAULT_POLLING_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=300)
        ),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wattbox."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        super().__init__()
        self._device_info = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await self._test_connection(user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        if not errors:
            # Create a better title using device information
            title = self._create_device_title(user_input[CONF_HOST])
            return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def _test_connection(self, user_input: dict[str, Any]) -> None:
        """Test connection to the device."""
        from .telnet_client import (
            WattboxAuthenticationError,
            WattboxConnectionError,
            WattboxTelnetClient,
        )

        telnet_client = WattboxTelnetClient(
            host=user_input[CONF_HOST],
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
        )

        try:
            await telnet_client.async_connect()
            # Get device information for better naming
            await telnet_client.async_get_device_info()
            await telnet_client.async_disconnect()

            # Store device info for use in entry title
            self._device_info = telnet_client.device_data.get("device_info", {})
        except WattboxAuthenticationError as err:
            _LOGGER.error("Authentication failed: %s", err)
            raise InvalidAuth from err
        except WattboxConnectionError as err:
            _LOGGER.error("Connection failed: %s", err)
            raise CannotConnect from err
        except Exception as err:
            _LOGGER.error("Unexpected error during connection test: %s", err)
            raise CannotConnect from err

    def _create_device_title(self, host: str) -> str:
        """Create a user-friendly device title."""
        device_info = getattr(self, "_device_info", {})

        # Try to get hostname first (most user-friendly)
        hostname = device_info.get("hostname")
        if hostname and hostname.strip():
            return hostname.strip()

        # Fall back to model if available
        model = device_info.get("model")
        if model and model.strip():
            return f"Wattbox {model.strip()}"

        # Fall back to service tag if available
        serial = device_info.get("serial_number")
        if serial and serial.strip():
            return f"Wattbox {serial.strip()}"

        # Final fallback to host
        return f"Wattbox {host}"

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return WattboxOptionsFlow(config_entry)


class WattboxOptionsFlow(config_entries.OptionsFlow):
    """Handle Wattbox options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is None:
            return self.async_show_form(
                step_id="init", data_schema=self._build_options_schema()
            )

        await self._apply_outlet_settings(user_input)
        return self.async_create_entry(title="", data=user_input)

    def _build_options_schema(self) -> vol.Schema:
        """Build dynamic options schema with per-outlet mode and name."""
        coordinator = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id)
        outlet_info = coordinator.data.get("outlet_info", []) if coordinator and coordinator.data else []
        if not outlet_info:
            outlet_info = [{"name": f"Outlet {i + 1}", "mode": 0} for i in range(18)]

        schema_fields: dict[Any, Any] = {}
        for i, outlet in enumerate(outlet_info, start=1):
            current_name = outlet.get(
                "name",
                self._config_entry.options.get(f"outlet_{i}_name", f"Outlet {i}"),
            )
            current_mode = outlet.get(
                "mode",
                self._config_entry.options.get(f"outlet_{i}_mode", 0),
            )

            schema_fields[vol.Optional(f"outlet_{i}_name", default=current_name)] = str
            schema_fields[vol.Optional(f"outlet_{i}_mode", default=current_mode)] = vol.In(
                {0: "Enabled", 1: "Disabled", 2: "Reset Only"}
            )

        return vol.Schema(schema_fields)

    async def _apply_outlet_settings(self, user_input: dict[str, Any]) -> None:
        """Apply changed outlet names and modes to device."""
        coordinator = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id)
        if not coordinator or not coordinator.data:
            return

        outlet_info = coordinator.data.get("outlet_info", [])
        for i, outlet in enumerate(outlet_info, start=1):
            new_name = str(user_input.get(f"outlet_{i}_name", outlet.get("name", ""))).strip()
            new_mode = int(user_input.get(f"outlet_{i}_mode", outlet.get("mode", 0)))

            current_name = str(outlet.get("name", "")).strip()
            current_mode = int(outlet.get("mode", 0))

            if new_name and new_name != current_name:
                await coordinator.telnet_client.async_set_outlet_name(i, new_name)

            if new_mode != current_mode:
                await coordinator.telnet_client.async_set_outlet_mode(i, new_mode)

        await coordinator.async_request_refresh()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
