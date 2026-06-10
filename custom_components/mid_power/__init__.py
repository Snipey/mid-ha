"""The Modesto Irrigation District integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MidApiClient, MidApiError, MidUsageData
from .const import (
    DOMAIN,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_ACCOUNT_ID,
    CONF_US_ID,
    POLL_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)

    client = MidApiClient(
        session,
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )

    token_data = entry.data.get("token_data", {})
    client.load_tokens(token_data)

    account_id = entry.data.get(CONF_ACCOUNT_ID, "")
    us_id = entry.data.get(CONF_US_ID, "")
    internal_user = entry.data.get(CONF_USERNAME, "")
    if account_id and us_id:
        client.restore_ids(account_id, us_id, internal_user)

    coordinator = MidUsageCoordinator(hass, client, entry)

    if us_id:
        await coordinator.async_config_entry_first_refresh()
    else:
        _LOGGER.warning("No US ID — skipping initial data fetch")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class MidUsageCoordinator(DataUpdateCoordinator[MidUsageData]):

    def __init__(self, hass: HomeAssistant, client: MidApiClient,
                 entry: ConfigEntry) -> None:
        self._client = client
        self._entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name="Modesto Irrigation District",
            update_interval=timedelta(minutes=POLL_INTERVAL_MINUTES),
        )

    async def _async_update_data(self) -> MidUsageData:
        try:
            data = await self._client.fetch_all_usage()
        except MidApiError as exc:
            _LOGGER.error("MID data fetch failed: %s", exc)
            self._maybe_update_tokens()
            raise UpdateFailed(str(exc)) from exc

        self._maybe_update_tokens()
        return data

    def _maybe_update_tokens(self) -> None:
        new_token_data = self._client._serialize_tokens()
        current_token_data = self._entry.data.get("token_data", {})
        if new_token_data != current_token_data:
            new_data = dict(self._entry.data)
            new_data["token_data"] = new_token_data
            self.hass.config_entries.async_update_entry(
                self._entry, data=new_data
            )
