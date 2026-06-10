"""Config flow for MID Power Usage integration."""

import logging
from typing import Any

import voluptuous as vol
from aiohttp import ClientSession

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MidApiClient, MidAuthError, MidAccountError, MidApiError
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_ACCOUNT_ID, CONF_US_ID

_LOGGER = logging.getLogger(__name__)

AUTH_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Required(CONF_ACCOUNT_ID): str,
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
            session = async_get_clientsession(self.hass)
            client = MidApiClient(
                session,
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[CONF_ACCOUNT_ID],
            )

            try:
                token_data = await client.authenticate()
                _LOGGER.debug("Auth succeeded, discovering account...")
                account_info = await client.discover_account()
            except MidAuthError:
                errors["base"] = "auth"
            except MidAccountError:
                errors["base"] = "account"
                token_data = client._serialize_tokens()
                await self.async_set_unique_id(user_input[CONF_ACCOUNT_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"MID Power ({user_input[CONF_ACCOUNT_ID]})",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_ACCOUNT_ID: user_input[CONF_ACCOUNT_ID],
                        CONF_US_ID: "",
                        "token_data": token_data,
                        "premise_info": "",
                    },
                )
            except MidApiError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"

            if not errors:
                us_id = account_info.us_id
                await self.async_set_unique_id(us_id)
                self._abort_if_unique_id_configured()

                title = f"MID Power ({account_info.premise_info or us_id})"

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_ACCOUNT_ID: user_input[CONF_ACCOUNT_ID],
                        CONF_US_ID: us_id,
                        "token_data": token_data,
                        "premise_info": account_info.premise_info,
                        "us_info": account_info.us_info,
                        "us_type": account_info.us_type_description,
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
