# MID Power Usage

Home Assistant integration for Modesto Irrigation District (MID) electric usage monitoring.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

## Features

- Retrieves monthly electric usage data from your MID account
- Provides sensors for:
  - Latest billing month usage (kWh)
  - Total period usage (kWh)
  - Average monthly usage (kWh)
  - Peak monthly usage (kWh)
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
2. Search for "MID Power Usage"
3. Enter your MID account credentials:
   - **Username**: Your MID internal username (found in network requests to `/cognito/auth` on the MID portal)
   - **Password**: Your MID MyAccount password
   - **Usage Service ID (US ID)**: Found by inspecting network requests for `getUsageDisplay` on the MID portal — look for `usId` in the request payload

### Finding your US ID

1. Log into [myaccount.mid.org](https://myaccount.mid.org)
2. Open browser DevTools (F12) → Network tab
3. Look for requests to `getUsageDisplay`
4. In the request payload, find the `usId` value (e.g. `781247994300`)

## Sensors

| Sensor | Description |
|--------|-------------|
| `sensor.mid_power_latest_monthly_usage` | kWh used in the most recent billing month |
| `sensor.mid_power_total_period_usage` | Total kWh across all retrieved billing months |
| `sensor.mid_power_average_monthly_usage` | Average kWh per billing month |
| `sensor.mid_power_peak_monthly_usage` | Highest single-month kWh in the period |
