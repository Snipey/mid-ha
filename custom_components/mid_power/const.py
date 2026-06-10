"""Constants for the MID Power Usage integration."""

DOMAIN = "mid_power"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_EMAIL = "email"
CONF_US_ID = "us_id"
CONF_ACCOUNT_ID = "account_id"
CONF_PREMISE_INFO = "premise_info"
CONF_US_TYPE = "us_type"

API_BASE_URL = "https://ocx-be-prod.myaccount.mid.org"
AUTH_URL = f"{API_BASE_URL}/cognito/auth"
REFRESH_URL = f"{API_BASE_URL}/cognito/refreshToken"
USAGE_URL = f"{API_BASE_URL}/ouaf/getUsageDisplay"
ACCOUNT_INFO_URL = f"{API_BASE_URL}/ouaf/accountInfo"
USERNAME_SEARCH_URL = f"{API_BASE_URL}/api/usernamesearch"

POLL_INTERVAL_MINUTES = 60

ATTR_READING_DATE = "reading_date"
ATTR_BILLING_PERIODS = "billing_periods"
ATTR_PERIOD_START = "period_start"
ATTR_PERIOD_END = "period_end"
ATTR_UOM = "uom"
ATTR_SQI = "sqi"
ATTR_HIGHEST_MONTH = "highest_month"
ATTR_LOWEST_MONTH = "lowest_month"
ATTR_PREMISE_INFO = "premise_info"
ATTR_US_TYPE = "us_type"

DISP_MODE = "D2BM"
DISP_MODE_DAILY = "D2BH"
UOM_KWH_D = "KWH-D"
SQI_CONSUMED = "CONSUMED"
OVERLAY_MODE = "D2TF"
