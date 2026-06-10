"""Config flow for Modesto Irrigation District integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MidApiClient, MidAuthError, MidAccountError, MidApiError
from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_EMAIL,
    CONF_ACCOUNT_ID,
    CONF_US_ID,
    CONF_PREMISE_INFO,
    CONF_US_TYPE,
)

_LOGGER = logging.getLogger(__name__)

AUTH_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_EMAIL): str,
    vol.Required(CONF_PASSWORD): str,
})


class MidPowerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = MidApiClient(
                session,
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[CONF_EMAIL],
            )

            try:
                token_data = await client.authenticate()
                _LOGGER.debug("Auth OK, discovering account...")
                account_info = await client.discover_account()
            except MidAuthError:
                errors["base"] = "auth"
            except MidAccountError as exc:
                errors["base"] = "account"
                _LOGGER.error("Account discovery failed: %s", exc)
            except MidApiError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(account_info.us_id)
                self._abort_if_unique_id_configured()

                title = account_info.premise_info or account_info.us_id
                _LOGGER.info("Discovered account: %s", title)

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_ACCOUNT_ID: account_info.account_id,
                        CONF_US_ID: account_info.us_id,
                        CONF_PREMISE_INFO: account_info.premise_info,
                        CONF_US_TYPE: account_info.us_type_description,
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
    def async_get_options_flow(config_entry):
        return MidPowerOptionsFlow(config_entry)


class MidPowerOptionsFlow(config_entries.OptionsFlow):

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )
