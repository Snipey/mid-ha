"""Config flow for MID Power Usage integration."""

import logging
from typing import Any

import voluptuous as vol
from aiohttp import ClientSession

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MidApiClient, MidAuthError, MidApiError
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_US_ID

_LOGGER = logging.getLogger(__name__)

AUTH_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Required(CONF_US_ID): str,
})


class MidPowerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MID Power Usage."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_US_ID])
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = MidApiClient(
                session,
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[CONF_US_ID],
            )
            try:
                token_data = await client.authenticate()
            except MidAuthError:
                errors["base"] = "auth"
            except MidApiError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected error during auth")
                errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title=f"MID Power ({user_input[CONF_US_ID]})",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_US_ID: user_input[CONF_US_ID],
                        "token_data": token_data,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=AUTH_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ):
        return MidPowerOptionsFlow(config_entry)


class MidPowerOptionsFlow(config_entries.OptionsFlow):
    """Options flow for MID Power Usage."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )
