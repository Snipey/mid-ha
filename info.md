# Modesto Irrigation District

Home Assistant integration for Modesto Irrigation District (MID) electric usage monitoring.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

## Features

- Retrieves monthly electric usage data from your MID account
- Daily usage monitoring with day-over-day comparison
- Provides sensors for:
  - Latest billing month usage (kWh)
  - Total period usage (kWh)
  - Average monthly usage (kWh)
  - Peak monthly usage (kWh)
  - Latest daily usage (kWh)
  - Average daily usage (kWh)
- Includes comparison to "normal" usage (overlay data from MID)
- Automatic token refresh for persistent access

## Installation

### HACS (recommended)

1. In HACS, go to Integrations
2. Click the three dots menu → Custom repositories
3. Add `https://github.com/Snipey/mid-ha` as category **Integration**
4. Click Install
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/mid_power/` directory into your `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Modesto Irrigation District"
3. Enter your MID account credentials:
   - **Username**: Your MID internal username (found in network requests to `/cognito/auth` on the MID portal)
   - **Email**: The email you use to log into MyAccount
   - **Password**: Your MID MyAccount password

The integration automatically discovers your account, billing info, and usage service.

## Sensors

| Sensor | Description |
|--------|-------------|
| `sensor.mid_power_latest_monthly_usage` | kWh used in the most recent billing month |
| `sensor.mid_power_total_period_usage` | Total kWh across all retrieved billing months |
| `sensor.mid_power_average_monthly_usage` | Average kWh per billing month |
| `sensor.mid_power_peak_monthly_usage` | Highest single-month kWh in the period |
| `sensor.mid_power_latest_daily_usage` | kWh used on the most recent day |
| `sensor.mid_power_average_daily_usage` | Average daily kWh over the past ~35 days |
