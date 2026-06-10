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
    CONF_US_ID,
    ATTR_READING_DATE,
    ATTR_BILLING_PERIODS,
    ATTR_PERIOD_START,
    ATTR_PERIOD_END,
    ATTR_UOM,
    ATTR_SQI,
    ATTR_HIGHEST_MONTH,
    ATTR_LOWEST_MONTH,
    ATTR_PREMISE_INFO,
    ATTR_US_TYPE,
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

    us_id = entry.data.get(CONF_US_ID, "")
    if not us_id:
        _LOGGER.warning("No US ID in config entry — skipping sensor setup")
        return

    async_add_entities([
        # Monthly sensors
        MidLatestMonthlySensor(coordinator, entry),
        MidTotalUsageSensor(coordinator, entry),
        MidAverageMonthlySensor(coordinator, entry),
        MidPeakMonthlySensor(coordinator, entry),
        # Daily sensors
        MidLatestDailySensor(coordinator, entry),
        MidAverageDailySensor(coordinator, entry),
    ])


class MidBaseSensor(CoordinatorEntity[MidUsageCoordinator], SensorEntity):
    """Base sensor for MID power usage."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_has_entity_name = True
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: MidUsageCoordinator,
                 entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = (
            f"{entry.data[CONF_US_ID]}_{self.entity_description.key}"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Modesto Irrigation District",
            "model": entry.data.get("us_type", "Residential"),
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def _monthly(self) -> list[UsagePeriod]:
        if self.coordinator.data is None:
            return []
        return self.coordinator.data.monthly_periods

    @property
    def _daily(self) -> list[UsagePeriod]:
        if self.coordinator.data is None:
            return []
        return self.coordinator.data.daily_periods

    @property
    def _overlay(self) -> list[OverlayPeriod]:
        if self.coordinator.data is None:
            return []
        return self.coordinator.data.overlay_periods

    def _build_monthly_attrs(self) -> dict:
        monthly = self._monthly
        attrs: dict = {
            ATTR_PREMISE_INFO: self._entry.data.get("premise_info", ""),
            ATTR_US_TYPE: self._entry.data.get("us_type", ""),
        }
        if not monthly:
            return attrs
        dates = [p.date for p in monthly]
        sorted_dates = sorted(dates)
        quantities = [p.quantity for p in monthly]
        peak = max(quantities)
        low = min(quantities)
        attrs.update({
            ATTR_BILLING_PERIODS: len(monthly),
            ATTR_PERIOD_START: _parse_date(sorted_dates[0]),
            ATTR_PERIOD_END: _parse_date(sorted_dates[-1]),
            ATTR_UOM: monthly[0].uom,
            ATTR_SQI: monthly[0].sqi,
            ATTR_HIGHEST_MONTH: _parse_date(
                monthly[quantities.index(peak)].date),
            ATTR_LOWEST_MONTH: _parse_date(
                monthly[quantities.index(low)].date),
        })
        return attrs


# --- Monthly sensors ---


class MidLatestMonthlySensor(MidBaseSensor):
    """Sensor for the most recent billing month usage."""

    entity_description = SensorEntityDescription(
        key="latest_monthly_usage",
        name="Latest monthly usage",
        icon="mdi:flash",
    )
    _attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> StateType:
        if self._monthly:
            return round(self._monthly[-1].quantity, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        attrs = self._build_monthly_attrs()
        monthly = self._monthly
        if monthly:
            latest = monthly[-1]
            attrs[ATTR_READING_DATE] = _parse_date(latest.date)
            overlay = self._overlay
            if overlay and len(overlay) == len(monthly):
                ov = overlay[-1]
                attrs["comparison_normal"] = ov.quantity
                attrs["comparison_min"] = ov.min_quantity
                attrs["comparison_max"] = ov.max_quantity
                attrs["difference_vs_normal"] = round(
                    latest.quantity - ov.quantity, 1)
        return attrs


class MidTotalUsageSensor(MidBaseSensor):
    """Sensor for total usage across all billing months."""

    entity_description = SensorEntityDescription(
        key="total_period_usage",
        name="Total period usage",
        icon="mdi:flash",
    )
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> StateType:
        if self._monthly:
            return round(sum(p.quantity for p in self._monthly), 1)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        return self._build_monthly_attrs()


class MidAverageMonthlySensor(MidBaseSensor):
    """Sensor for average monthly usage."""

    entity_description = SensorEntityDescription(
        key="average_monthly_usage",
        name="Average monthly usage",
        icon="mdi:flash",
    )
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> StateType:
        if self._monthly:
            return round(
                sum(p.quantity for p in self._monthly) / len(self._monthly), 1)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        return self._build_monthly_attrs()


class MidPeakMonthlySensor(MidBaseSensor):
    """Sensor for the highest single-month usage."""

    entity_description = SensorEntityDescription(
        key="peak_monthly_usage",
        name="Peak monthly usage",
        icon="mdi:flash-alert",
    )
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> StateType:
        if self._monthly:
            return round(max(p.quantity for p in self._monthly), 1)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        return self._build_monthly_attrs()


# --- Daily sensors ---


class MidLatestDailySensor(MidBaseSensor):
    """Sensor for the most recent daily usage."""

    entity_description = SensorEntityDescription(
        key="latest_daily_usage",
        name="Latest daily usage",
        icon="mdi:flash-outline",
    )
    _attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> StateType:
        if self._daily:
            return round(self._daily[-1].quantity, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        daily = self._daily
        attrs: dict = {}
        if daily:
            latest = daily[-1]
            attrs[ATTR_READING_DATE] = _parse_date(latest.date)
            attrs["days_in_period"] = len(daily)
            if len(daily) >= 2:
                prev = daily[-2]
                attrs["previous_day"] = round(prev.quantity, 1)
                attrs["day_change_pct"] = round(
                    (latest.quantity - prev.quantity) / prev.quantity * 100, 1
                ) if prev.quantity else 0
        return attrs


class MidAverageDailySensor(MidBaseSensor):
    """Sensor for average daily usage over the period."""

    entity_description = SensorEntityDescription(
        key="average_daily_usage",
        name="Average daily usage",
        icon="mdi:flash-outline",
    )
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> StateType:
        if self._daily:
            return round(
                sum(p.quantity for p in self._daily) / len(self._daily), 1)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        daily = self._daily
        attrs: dict = {}
        if daily:
            attrs["days_in_period"] = len(daily)
            quantities = [p.quantity for p in daily]
            attrs["peak_daily"] = round(max(quantities), 1)
            attrs["lowest_daily"] = round(min(quantities), 1)
            peak_day = _parse_date(daily[quantities.index(max(quantities))].date)
            attrs["peak_day_date"] = peak_day
        return attrs
