"""OAuth2 token management for Omada API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from .exceptions import OmadaAuthenticationError, OmadaConnectionError


class OAuth2TokenManager:
    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        omadac_id: str,
        verify: bool = True,
        timeout: float = 30.0,
        token_refresh_buffer: int = 300,
    ) -> None:
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.omadac_id = omadac_id
        self.verify = verify
        self.timeout = timeout
        self.token_refresh_buffer = token_refresh_buffer
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    def clear_token(self) -> None:
        self._access_token = None
        self._token_expires_at = None

    def _is_token_valid(self) -> bool:
        if not self._access_token or not self._token_expires_at:
            return False
        return datetime.now(timezone.utc) < self._token_expires_at

    def get_token(self) -> str:
        if self._is_token_valid():
            return self._access_token or ""
        self._fetch_token()
        return self._access_token or ""

    def get_headers(self) -> dict[str, str]:
        token = self.get_token()
        return {"Authorization": f"AccessToken={token}"}

    def _fetch_token(self) -> None:
        try:
            response = httpx.post(
                self.token_url,
                timeout=self.timeout,
                verify=self.verify,
                params={"grant_type": "client_credentials"},
                json={
                    "omadacId": self.omadac_id,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/json"},
            )
        except httpx.RequestError as exc:
            raise OmadaConnectionError(
                "Failed to fetch OAuth2 token",
                original_error=exc,
            ) from exc

        payload = _safe_json(response)
        if response.status_code >= 400:
            raise OmadaAuthenticationError(
                _token_failure_message(
                    status_code=response.status_code,
                    payload=payload,
                ),
                status_code=response.status_code,
                response_data=payload,
            )

        if payload.get("errorCode") not in (None, 0):
            raise OmadaAuthenticationError(
                _token_failure_message(
                    status_code=response.status_code,
                    payload=payload,
                ),
                status_code=response.status_code,
                response_data=payload,
            )

        token = payload.get("access_token") or payload.get("result", {}).get("accessToken")
        expires_in = payload.get("expires_in") or payload.get("result", {}).get("expiresIn", 3600)
        if not token:
            raise OmadaAuthenticationError(
                _token_failure_message(
                    status_code=response.status_code,
                    payload=payload,
                    default="Token response missing access_token",
                ),
                response_data=payload,
            )

        refresh_before_expiry = max(int(expires_in) - self.token_refresh_buffer, 0)
        self._access_token = token
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=refresh_before_expiry)


def _safe_json(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {"raw": response.text}
    if isinstance(payload, dict):
        return payload
    return {"raw": payload}


def _token_failure_message(
    status_code: int,
    payload: dict,
    default: str | None = None,
) -> str:
    mode = "local controller token request failed"
    if isinstance(payload, dict):
        error_code = payload.get("errorCode")
        message = payload.get("msg") or payload.get("message") or payload.get("error_description")
        if error_code is not None or message:
            return f"{mode}: errorCode={error_code} msg={message}"
    return default or f"{mode}: HTTP {status_code}"
