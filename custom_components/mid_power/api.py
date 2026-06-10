"""API client for Modesto Irrigation District (MID) power usage."""

from __future__ import annotations

import base64
import hashlib
import json as json_mod
import logging
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass

from aiohttp import ClientSession, ClientError

from .const import (
    AUTH_URL,
    REFRESH_URL,
    USAGE_URL,
    DISP_MODE,
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


@dataclass
class UsagePeriod:
    """A single billing period usage record."""
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
    usage_periods: list[UsagePeriod]
    overlay_periods: list[OverlayPeriod]
    channels: dict
    raw: dict


class MidApiError(Exception):
    """Error from the MID API."""


class MidAuthError(MidApiError):
    """Authentication error."""


class MidApiClient:
    """Async client for the MID API."""

    def __init__(self, session: ClientSession, username: str, password: str,
                 us_id: str):
        self._session = session
        self._username = username
        self._password = password
        self._us_id = us_id

        stored = (hashlib.sha256(username.encode()).hexdigest() +
                  hashlib.sha256(us_id.encode()).hexdigest())
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
        """Refresh the access token."""
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
                _LOGGER.debug("Refresh status=%s body=%s", resp.status, body[:500])
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

    # --- usage data ---

    async def fetch_all_usage(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> MidUsageData:
        """Fetch both usage periods and overlay data in one call."""
        await self._ensure_auth()

        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime(
                "%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

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

        raw_data = await self._post_usage({"payload": payload_data})
        return self._parse_usage_response(raw_data)

    async def _post_usage(self, payload: dict) -> dict:
        headers = {}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        try:
            async with self._session.post(
                USAGE_URL, json=payload, headers=headers,
                raise_for_status=False,
            ) as resp:
                body = await resp.text()
                _LOGGER.debug("Usage status=%s body_len=%s",
                              resp.status, len(body))
                if resp.status == 401:
                    self._access_token = None
                    self._token_expires = None
                    await self._ensure_auth()
                    return await self._post_usage(payload)
                if resp.status != 200:
                    raise MidApiError(
                        f"Usage request failed: HTTP {resp.status}")
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
            usage_periods=usage_periods,
            overlay_periods=overlay_periods,
            channels=channels,
            raw=data,
        )
