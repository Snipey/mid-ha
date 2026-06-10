# MID Power Usage

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Home Assistant custom integration for monitoring electric usage from Modesto Irrigation District (MID).

## Sensors

| Sensor | Description |
|--------|-------------|
| `sensor.mid_power_latest_monthly_usage` | kWh used in the most recent billing month |
| `sensor.mid_power_total_period_usage` | Total kWh across all retrieved billing months |
| `sensor.mid_power_average_monthly_usage` | Average kWh per billing month |
| `sensor.mid_power_peak_monthly_usage` | Highest single-month kWh in the period |

The latest usage sensor also includes comparison attributes: `comparison_normal`, `comparison_min`, `comparison_max`, and `difference_vs_normal`.

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
2. Search for "MID Power Usage"
3. Fill in the form:

| Field | How to find it |
|-------|----------------|
| **Username** | Log into [myaccount.mid.org](https://myaccount.mid.org), open DevTools (F12) → Network tab, look for a request to `/cognito/auth`, find `username` in the request payload |
| **Password** | Your MID MyAccount password |
| **US ID** | In the Network tab, look for requests to `getUsageDisplay`, find `usId` in the request payload (e.g. `781247994300`) |

### Step-by-step: finding your credentials

![finding-usid](https://via.placeholder.com/800x400?text=DevTools+Network+Tab+-+getUsageDisplay+request)

1. Log into [myaccount.mid.org](https://myaccount.mid.org)
2. Press **F12** to open browser DevTools
3. Go to the **Network** tab
4. Find a request to **getUsageDisplay**
5. Click it, then go to the **Payload** tab
6. Copy the `usId` value
7. Find a request to **cognito/auth** to get your `username`

## Dashboard Example

```yaml
type: entities
title: MID Power
entities:
  - entity: sensor.mid_power_latest_monthly_usage
  - entity: sensor.mid_power_total_period_usage
  - entity: sensor.mid_power_average_monthly_usage
  - entity: sensor.mid_power_peak_monthly_usage
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
- Verify your username, password, and US ID are correct
- The internal username is case-sensitive and may look like a random string (e.g. `DX7RN2vLgqDq459nTsey0b2PT26e8rt3`)
- Make sure your MID account is active at [myaccount.mid.org](https://myaccount.mid.org)

**No data after setup**
- The integration polls every 60 minutes — wait for the first update or reload the integration
- Check Home Assistant logs for errors

**Token expired / re-auth required**
- Tokens are refreshed automatically. If refresh fails, you may need to reconfigure the integration with your current credentials
