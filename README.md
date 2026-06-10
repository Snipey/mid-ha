# Modesto Irrigation District

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Home Assistant custom integration for monitoring electric usage from Modesto Irrigation District (MID).

## Sensors

### Monthly

| Sensor | Description |
|--------|-------------|
| `sensor.mid_power_latest_monthly_usage` | kWh used in the most recent billing month |
| `sensor.mid_power_total_period_usage` | Total kWh across all retrieved billing months |
| `sensor.mid_power_average_monthly_usage` | Average kWh per billing month |
| `sensor.mid_power_peak_monthly_usage` | Highest single-month kWh in the period |

### Daily

| Sensor | Description |
|--------|-------------|
| `sensor.mid_power_latest_daily_usage` | kWh used on the most recent day |
| `sensor.mid_power_average_daily_usage` | Average daily kWh over the past ~35 days |

The latest monthly sensor also includes comparison attributes: `comparison_normal`, `comparison_min`, `comparison_max`, and `difference_vs_normal`. The latest daily sensor includes `previous_day` and `day_change_pct`.

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the three-dot menu (top right) → **Custom repositories**
4. Enter `https://github.com/Snipey/mid-ha` as the repository URL
5. Set category to **Integration**
6. Click **Add**
7. In HACS, search for "MID Power Usage" and click **Download**
8. **Restart Home Assistant**

### Manual

1. Copy `custom_components/mid_power/` into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

After installation and restart:

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Modesto Irrigation District"
3. Enter your credentials:

| Field | How to find it |
|-------|----------------|
| **Username** | Log into [myaccount.mid.org](https://myaccount.mid.org), open DevTools (F12) → Network tab, look for a request to `/cognito/auth`, find `username` in the request payload |
| **Email** | The email address you use to log into MyAccount |
| **Password** | Your MID MyAccount password |

The integration will automatically discover your account, usage service, and premise info — no need to hunt through DevTools for IDs.

### Finding your username

1. Log into [myaccount.mid.org](https://myaccount.mid.org)
2. Press **F12** to open browser DevTools
3. Go to the **Network** tab
4. Find the request to **cognito/auth**
5. Click it, then go to the **Payload** tab
6. Copy the `username` value (a random-looking string like `DX7RN2vLgqDq459nTsey0b2PT26e8rt3`)

## Dashboard Example

```yaml
type: entities
title: MID Power
entities:
  - entity: sensor.mid_power_latest_monthly_usage
  - entity: sensor.mid_power_total_period_usage
  - entity: sensor.mid_power_average_monthly_usage
  - entity: sensor.mid_power_peak_monthly_usage
  - entity: sensor.mid_power_latest_daily_usage
  - entity: sensor.mid_power_average_daily_usage
```

Or with mini-graph-card:

```yaml
type: custom:mini-graph-card
name: MID Monthly Usage
entities:
  - sensor.mid_power_latest_monthly_usage
hours_to_show: 8760
points_per_hour: 0.004
line_width: 2
```

## Troubleshooting

**"Authentication failed" during setup**
- Verify your username and password are correct
- The internal username is case-sensitive and may look like a random string (e.g. `DX7RN2vLgqDq459nTsey0b2PT26e8rt3`)
- Make sure your MID account is active at [myaccount.mid.org](https://myaccount.mid.org)

**"Account discovery failed" during setup**
- The `/api/usernamesearch` response format may have changed
- Check Home Assistant logs for the raw usernamesearch response
- Open a GitHub issue with the log output (redact tokens)

**No data after setup**
- The integration polls every 60 minutes — wait for the first update or reload the integration
- Check Home Assistant logs for errors

**Token expired / re-auth required**
- Tokens are refreshed automatically. If refresh fails, you may need to reconfigure the integration with your current credentials
