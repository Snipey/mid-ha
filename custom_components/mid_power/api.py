"""API client for Modesto Irrigation District (MID) power usage."""

from __future__ import annotations

import base64
import hashlib
import json as json_mod
import logging
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from aiohttp import ClientSession, ClientError

from .const import (
    AUTH_URL,
    REFRESH_URL,
    USAGE_URL,
    ACCOUNT_INFO_URL,
    DISP_MODE,
    DISP_MODE_DAILY,
    UOM_KWH_D,
    SQI_CONSUMED,
    OVERLAY_MODE,
)

_LOGGER = logging.getLogger(__name__)


def _encode_username(username: str) -> str:
    return base64.b64encode(username.encode()).decode()


def _parse_body(body: str) -> dict:
    if not body or not body.strip():
        return {}
    try:
        data = json_mod.loads(body)
        return data if isinstance(data, dict) else {}
    except (json_mod.JSONDecodeError, TypeError, ValueError):
        return {}


# --- data types ---


@dataclass
class AccountInfo:
    """Discovered account information from the MID API."""
    us_id: str = ""
    us_external_id: str = ""
    premise_info: str = ""
    us_info: str = ""
    us_type: str = ""
    us_type_description: str = ""
    customer_name: str = ""
    address_line1: str = ""
    city: str = ""
    state: str = ""
    postal: str = ""
    bill_amount: str = "0.00"
    bill_due_date: str = ""


@dataclass
class UsagePeriod:
    """A single usage period record (monthly or daily)."""
    date: str
    uom: str
    tou: str
    sqi: str
    quantity: float


@dataclass
class OverlayPeriod:
    """A single overlay/comparison period record."""
    date: str
    quantity: float
    min_quantity: float
    max_quantity: float


@dataclass
class MidUsageData:
    """Parsed usage data from the MID API."""
    monthly_periods: list[UsagePeriod] = field(default_factory=list)
    daily_periods: list[UsagePeriod] = field(default_factory=list)
    overlay_periods: list[OverlayPeriod] = field(default_factory=list)
    channels: dict = field(default_factory=dict)


# --- errors ---


class MidApiError(Exception):
    """Error from the MID API."""


class MidAuthError(MidApiError):
    """Authentication error."""


class MidAccountError(MidApiError):
    """Account lookup error."""


# --- client ---


class MidApiClient:
    """Async client for the MID API."""

    def __init__(self, session: ClientSession, username: str, password: str,
                 account_id: str):
        self._session = session
        self._username = username
        self._password = password
        self._account_id = account_id
        self._us_id: str | None = None

        stored = (hashlib.sha256(username.encode()).hexdigest() +
                  hashlib.sha256(account_id.encode()).hexdigest())
        device_uuid = str(uuid.UUID(
            stored[0:8] + "-" + stored[8:12] + "-" +
            stored[12:16] + "-" + stored[16:20] + "-" +
            stored[20:32]
        ))
        self._device_key = f"us-east-2_{device_uuid}"

        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._id_token: str | None = None
        self._token_expires: datetime | None = None

    @property
    def us_id(self) -> str | None:
        return self._us_id

    def set_us_id(self, us_id: str) -> None:
        self._us_id = us_id

    # --- token management ---

    def _serialize_tokens(self) -> dict:
        return {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "id_token": self._id_token,
            "token_expires": self._token_expires.isoformat()
            if self._token_expires else None,
        }

    @staticmethod
    def _deserialize_tokens(data: dict) -> tuple:
        access = data.get("access_token")
        refresh = data.get("refresh_token")
        id_tok = data.get("id_token")
        expires_str = data.get("token_expires")
        expires = (datetime.fromisoformat(expires_str)
                   if expires_str else None)
        return access, refresh, id_tok, expires

    def load_tokens(self, token_data: dict) -> None:
        access, refresh, id_tok, expires = self._deserialize_tokens(token_data)
        self._access_token = access
        self._refresh_token = refresh
        self._id_token = id_tok
        self._token_expires = expires

    async def authenticate(self) -> dict:
        """Authenticate and return token data for storage."""
        _LOGGER.debug("Authenticating with MID...")
        payload = {
            "username": self._username,
            "password": self._password,
        }
        try:
            async with self._session.post(
                AUTH_URL, json=payload, raise_for_status=False
            ) as resp:
                body = await resp.text()
                _LOGGER.debug("Auth status=%s body=%s", resp.status, body[:500])
                if resp.status != 200:
                    raise MidAuthError(
                        f"Auth failed: HTTP {resp.status} - {body[:300]}")
                data = _parse_body(body)
        except ClientError as exc:
            raise MidApiError(f"Connection error during auth: {exc}") from exc

        return self._store_auth_tokens(data)

    def _store_auth_tokens(self, data: dict) -> dict:
        result = data.get("result", data)
        if isinstance(result, dict):
            access = (result.get("access_token") or
                      result.get("AccessToken") or
                      result.get("token") or "")
            refresh = (result.get("refresh_token") or
                       result.get("RefreshToken") or "")
            id_tok = (result.get("id_token") or
                      result.get("IdToken") or "")
            expires_in = (result.get("expires_in") or
                          result.get("ExpiresIn") or 3600)
        else:
            access = refresh = id_tok = ""
            expires_in = 3600

        if access and not isinstance(access, str):
            access = str(access)
        self._access_token = access
        if refresh:
            self._refresh_token = refresh
        if id_tok:
            self._id_token = id_tok
        self._token_expires = datetime.now() + timedelta(
            seconds=min(int(expires_in or 3600), 3600))
        return self._serialize_tokens()

    async def _refresh_access_token(self) -> dict | None:
        if not self._access_token:
            return None

        encoded_user = _encode_username(self._username)
        payload = {
            "token": self._access_token,
            "username": encoded_user,
            "deviceKey": self._device_key,
        }
        _LOGGER.debug("Refreshing token...")
        try:
            async with self._session.post(
                REFRESH_URL, json=payload, raise_for_status=False
            ) as resp:
                body = await resp.text()
                _LOGGER.debug("Refresh status=%s body=%s",
                              resp.status, body[:500])
                if resp.status != 200:
                    _LOGGER.warning("Token refresh failed: %s", body[:200])
                    return None
                data = _parse_body(body)
        except ClientError as exc:
            _LOGGER.warning("Connection error during token refresh: %s", exc)
            return None

        result = data.get("result", data)
        if isinstance(result, dict):
            token = (result.get("access_token") or result.get("AccessToken") or
                     result.get("token") or result.get("id_token") or
                     result.get("IdToken") or "")
            expires_in = (result.get("expires_in") or
                          result.get("ExpiresIn") or 3600)
        else:
            return None

        if token and not isinstance(token, str):
            token = str(token)
        if token:
            self._access_token = token
            self._token_expires = datetime.now() + timedelta(
                seconds=min(int(expires_in or 3600), 3600))
            return self._serialize_tokens()
        return None

    async def _ensure_auth(self) -> None:
        if self._token_expires and datetime.now() < self._token_expires:
            return
        if self._access_token:
            new_tokens = await self._refresh_access_token()
            if new_tokens:
                return
        tokens = await self.authenticate()
        self.load_tokens(tokens)

    # --- account discovery ---

    async def discover_account(self) -> AccountInfo:
        """Discover account details and US ID from MID API."""
        await self._ensure_auth()

        result = AccountInfo()

        detail_data = await self._post_json(ACCOUNT_INFO_URL, {
            "payload": {"accounts": [{"accountId": self._account_id}]}
        })
        if isinstance(detail_data, dict):
            addr = detail_data.get("addressInfo", {})
            if isinstance(addr, dict):
                result.customer_name = detail_data.get(
                    "mainCustomerName", "")
                result.address_line1 = addr.get("addressLine1", "")
                result.city = addr.get("city", "")
                result.state = addr.get("state", "")
                result.postal = addr.get("postal", "")
            bill = detail_data.get("billInfo", {})
            if isinstance(bill, dict):
                result.bill_amount = bill.get("totalAmount", "0.00")
                result.bill_due_date = bill.get("dueDate", "")

        sub_data = await self._post_json(USAGE_URL, {
            "payload": {"accountId": self._account_id}
        })
        if isinstance(sub_data, dict):
            sub = sub_data.get("usageSubscriptions", {})
            if isinstance(sub, dict):
                us_id = sub.get("usId", "")
                if us_id:
                    self._us_id = us_id
                result.us_id = us_id
                result.us_external_id = sub.get("usExternalId", "")
                result.premise_info = sub.get("premiseInfo", "")
                result.us_info = sub.get("usInfo", "")
                result.us_type = sub.get("usType", "")
                result.us_type_description = sub.get(
                    "usTypeDescription", "")

        if not result.us_id:
            raise MidAccountError(
                "No usage subscriptions found for this account")

        return result

    # --- usage data ---

    async def fetch_all_usage(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> MidUsageData:
        """Fetch monthly, overlay, and daily usage data."""
        await self._ensure_auth()

        if not self._us_id:
            raise MidApiError("US ID not set — call discover_account first")

        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime(
                "%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        monthly = await self._fetch_monthly_usage(start_date, end_date)
        daily = await self._fetch_daily_usage()

        return MidUsageData(
            monthly_periods=monthly.usage_periods,
            daily_periods=daily.usage_periods,
            overlay_periods=monthly.overlay_periods,
            channels=monthly.channels,
        )

    async def _fetch_monthly_usage(self, start_date: str,
                                   end_date: str) -> MidUsageData:
        payload_data = {
            "usId": self._us_id,
            "startDate": start_date,
            "endDate": end_date,
            "displayMode": DISP_MODE,
            "uom": UOM_KWH_D,
            "tou": "",
            "sqi": SQI_CONSUMED,
            "netMeteringGroup": "",
            "overlayMode": OVERLAY_MODE,
            "measuringComponentId": "",
            "isTotalizationChannel": "",
        }
        raw = await self._post_json(USAGE_URL, {"payload": payload_data})
        return self._parse_usage_response(raw)

    async def _fetch_daily_usage(self,
                                 start_date: str | None = None,
                                 end_date: str | None = None) -> MidUsageData:
        if not start_date:
            start_date = (datetime.now() - timedelta(days=35)).strftime(
                "%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        payload_data = {
            "usId": self._us_id,
            "startDate": start_date,
            "endDate": end_date,
            "displayMode": DISP_MODE_DAILY,
            "uom": UOM_KWH_D,
            "tou": "",
            "sqi": SQI_CONSUMED,
            "netMeteringGroup": "",
            "measuringComponentId": "",
            "isTotalizationChannel": "",
        }
        raw = await self._post_json(USAGE_URL, {"payload": payload_data})
        return self._parse_usage_response(raw)

    # --- HTTP helpers ---

    async def _post_json(self, url: str, payload: dict) -> dict:
        headers = {}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        try:
            async with self._session.post(
                url, json=payload, headers=headers,
                raise_for_status=False,
            ) as resp:
                body = await resp.text()
                if resp.status == 401:
                    self._access_token = None
                    self._token_expires = None
                    await self._ensure_auth()
                    return await self._post_json(url, payload)
                if resp.status != 200:
                    raise MidApiError(
                        f"Request failed: HTTP {resp.status}")
                return _parse_body(body)
        except ClientError as exc:
            raise MidApiError(f"Connection error: {exc}") from exc

    @staticmethod
    def _parse_usage_response(data: dict) -> MidUsageData:
        usage_periods: list[UsagePeriod] = []
        overlay_periods: list[OverlayPeriod] = []
        channels: dict = {}

        usage_data = data.get("usagePeriods", {})
        if isinstance(usage_data, dict):
            for period in usage_data.get("periods", []):
                if not isinstance(period, dict):
                    continue
                try:
                    usage_periods.append(UsagePeriod(
                        date=period.get("dateTime", ""),
                        uom=period.get("uom", ""),
                        tou=period.get("tou", ""),
                        sqi=period.get("sqi", ""),
                        quantity=float(period.get("quantity", 0)),
                    ))
                except (ValueError, TypeError):
                    continue

        overlay_data = data.get("overlayQuantities", {})
        if isinstance(overlay_data, dict):
            for period in overlay_data.get("periods", []):
                if not isinstance(period, dict):
                    continue
                try:
                    overlay_periods.append(OverlayPeriod(
                        date=period.get("dateTime", ""),
                        quantity=float(period.get("quantity", 0)),
                        min_quantity=float(period.get("minQuantity", 0)),
                        max_quantity=float(period.get("maxQuantity", 0)),
                    ))
                except (ValueError, TypeError):
                    continue

        channels = data.get("channels", {})
        if not isinstance(channels, dict):
            channels = {}

        return MidUsageData(
            monthly_periods=usage_periods,
            overlay_periods=overlay_periods,
            channels=channels,
        )
