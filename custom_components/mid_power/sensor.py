"""Sensor platform for MID Power Usage."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MidUsageCoordinator
from .api import UsagePeriod, OverlayPeriod
from .const import (
    DOMAIN,
    ATTR_READING_DATE,
    ATTR_BILLING_PERIODS,
    ATTR_PERIOD_START,
    ATTR_PERIOD_END,
    ATTR_UOM,
    ATTR_SQI,
    ATTR_HIGHEST_MONTH,
    ATTR_LOWEST_MONTH,
)

_LOGGER = logging.getLogger(__name__)


def _parse_date(date_str: str) -> str:
    """Parse MID date format YYYY-MM-DD-HH.MM.SS to YYYY-MM-DD."""
    for fmt in ("%Y-%m-%d-%H.%M.%S", "%Y-%m-%d-%H.%M.%S.%f"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(date_str).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass
    try:
        return date_str[:10]
    except (TypeError, IndexError):
        return date_str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MID Power sensors."""
    domain_data = hass.data[DOMAIN]
    coordinator = domain_data[entry.entry_id]["coordinator"]

    entities: list[SensorEntity] = [
        MidLatestUsageSensor(coordinator, entry),
        MidTotalUsageSensor(coordinator, entry),
        MidAverageUsageSensor(coordinator, entry),
        MidPeakUsageSensor(coordinator, entry),
    ]
    async_add_entities(entities)


class MidUsageBaseSensor(CoordinatorEntity[MidUsageCoordinator], SensorEntity):
    """Base sensor for MID power usage."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_has_entity_name = True

    def __init__(self, coordinator: MidUsageCoordinator,
                 entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = (
            f"{entry.data['us_id']}_{self.entity_description.key}"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "MID Power Usage",
            "manufacturer": "Modesto Irrigation District",
            "model": "Usage Service",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def _usage_periods(self) -> list[UsagePeriod]:
        if self.coordinator.data is None:
            return []
        return self.coordinator.data.usage_periods

    @property
    def _overlay_periods(self) -> list[OverlayPeriod]:
        if self.coordinator.data is None:
            return []
        return self.coordinator.data.overlay_periods

    @property
    def _channels(self) -> dict:
        if self.coordinator.data is None:
            return {}
        return self.coordinator.data.channels

    def _build_base_attrs(self) -> dict:
        usage = self._usage_periods
        if not usage:
            return {}
        dates = [p.date for p in usage]
        sorted_dates = sorted(dates)
        quantities = [p.quantity for p in usage]
        peak = max(quantities)
        low = min(quantities)
        return {
            ATTR_BILLING_PERIODS: len(usage),
            ATTR_PERIOD_START: _parse_date(sorted_dates[0]) if sorted_dates else None,
            ATTR_PERIOD_END: _parse_date(sorted_dates[-1]) if sorted_dates else None,
            ATTR_UOM: usage[0].uom if usage else None,
            ATTR_SQI: usage[0].sqi if usage else None,
            ATTR_HIGHEST_MONTH: _parse_date(
                usage[quantities.index(peak)].date
            ) if usage else None,
            ATTR_LOWEST_MONTH: _parse_date(
                usage[quantities.index(low)].date
            ) if usage else None,
        }


class MidLatestUsageSensor(MidUsageBaseSensor):
    """Sensor for the most recent billing month usage."""

    entity_description = SensorEntityDescription(
        key="latest_monthly_usage",
        name="Latest monthly usage",
        icon="mdi:flash",
    )

    @property
    def native_value(self) -> StateType:
        usage = self._usage_periods
        if usage:
            return round(usage[-1].quantity, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        attrs = self._build_base_attrs()
        usage = self._usage_periods
        if usage:
            latest = usage[-1]
            attrs[ATTR_READING_DATE] = _parse_date(latest.date)
            overlay = self._overlay_periods
            if overlay and len(overlay) == len(usage):
                ov = overlay[-1]
                attrs["comparison_normal"] = ov.quantity
                attrs["comparison_min"] = ov.min_quantity
                attrs["comparison_max"] = ov.max_quantity
                diff = latest.quantity - ov.quantity
                attrs["difference_vs_normal"] = round(diff, 1)
        return attrs


class MidTotalUsageSensor(MidUsageBaseSensor):
    """Sensor for total usage across all retrieved billing months."""

    entity_description = SensorEntityDescription(
        key="total_period_usage",
        name="Total period usage",
        icon="mdi:flash",
    )

    @property
    def native_value(self) -> StateType:
        usage = self._usage_periods
        if usage:
            return round(sum(p.quantity for p in usage), 1)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        return self._build_base_attrs()


class MidAverageUsageSensor(MidUsageBaseSensor):
    """Sensor for average monthly usage."""

    entity_description = SensorEntityDescription(
        key="average_monthly_usage",
        name="Average monthly usage",
        icon="mdi:flash",
    )

    @property
    def native_value(self) -> StateType:
        usage = self._usage_periods
        if usage:
            return round(sum(p.quantity for p in usage) / len(usage), 1)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        return self._build_base_attrs()


class MidPeakUsageSensor(MidUsageBaseSensor):
    """Sensor for the highest single-month usage."""

    entity_description = SensorEntityDescription(
        key="peak_monthly_usage",
        name="Peak monthly usage",
        icon="mdi:flash-alert",
    )

    @property
    def native_value(self) -> StateType:
        usage = self._usage_periods
        if usage:
            return round(max(p.quantity for p in usage), 1)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        return self._build_base_attrs()
