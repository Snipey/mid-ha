"""The MID Power Usage integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MidApiClient, MidApiError, MidUsageData
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_US_ID, POLL_INTERVAL_MINUTES

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MID Power Usage from a config entry."""
    session = async_get_clientsession(hass)

    client = MidApiClient(
        session,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_US_ID],
    )
    token_data = entry.data.get("token_data", {})
    client.load_tokens(token_data)

    coordinator = MidUsageCoordinator(hass, client, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    entry.async_on_unload(
        entry.add_update_listener(async_update_listener)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class MidUsageCoordinator(DataUpdateCoordinator[MidUsageData]):
    """Coordinator to fetch MID power usage data."""

    def __init__(self, hass: HomeAssistant, client: MidApiClient,
                 entry: ConfigEntry) -> None:
        self._client = client
        self._entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name="MID Power Usage",
            update_interval=timedelta(minutes=POLL_INTERVAL_MINUTES),
        )

    async def _async_update_data(self) -> MidUsageData:
        try:
            data = await self._client.fetch_all_usage()
        except MidApiError as exc:
            raise UpdateFailed(f"Error fetching usage: {exc}") from exc

        new_token_data = self._client._serialize_tokens()
        current_token_data = self._entry.data.get("token_data", {})
        if new_token_data != current_token_data:
            new_data = dict(self._entry.data)
            new_data["token_data"] = new_token_data
            self.hass.config_entries.async_update_entry(
                self._entry, data=new_data
            )

        return data
