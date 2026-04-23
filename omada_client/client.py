"""Main Omada API client."""

from __future__ import annotations

from typing import Any

import httpx

from .auth import OAuth2TokenManager
from .config import resolve_endpoint_config
from .exceptions import (
    OmadaAPIError,
    OmadaAuthenticationError,
    OmadaConnectionError,
    OmadaNotFoundError,
    OmadaPermissionError,
    OmadaValidationError,
)
from .logging_config import format_body, get_logger, mask_sensitive_headers, set_log_level
from .resources import APGroupsResource, APsResource, DevicesResource, SitesResource, WiFiNetworksResource


class OmadaClient:
    def __init__(
        self,
        base_url: str,
        omadac_id: str,
        client_id: str,
        client_secret: str,
        token_url: str | None = None,
        verify: bool = True,
        timeout: float = 30.0,
        max_retries: int = 2,
        enable_retry: bool = True,
        log_level: str = "INFO",
    ) -> None:
        if not omadac_id:
            raise ValueError("omadac_id is required")
        set_log_level(log_level)
        endpoint_config = resolve_endpoint_config(
            base_url=base_url,
            token_url=token_url,
        )
        self.logger = get_logger()
        self.omadac_id = omadac_id
        self.verify = verify
        self.timeout = timeout
        self.max_retries = max_retries
        self.enable_retry = enable_retry

        self.auth = OAuth2TokenManager(
            token_url=endpoint_config.token_url,
            client_id=client_id,
            client_secret=client_secret,
            omadac_id=omadac_id,
            verify=verify,
            timeout=timeout,
        )
        self._http = httpx.Client(base_url=endpoint_config.api_base_url, timeout=timeout, verify=verify)

        self.sites = SitesResource(self)
        self.devices = DevicesResource(self)
        self.aps = APsResource(self)
        self.wifi_networks = WiFiNetworksResource(self)
        self.ap_groups = APGroupsResource(self)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "OmadaClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request_with_retry("GET", path, params=params)

    def post(self, path: str, json: Any | None = None) -> dict[str, Any]:
        return self._request_with_retry("POST", path, json=json)

    def put(self, path: str, json: Any | None = None) -> dict[str, Any]:
        return self._request_with_retry("PUT", path, json=json)

    def patch(self, path: str, json: Any | None = None) -> dict[str, Any]:
        return self._request_with_retry("PATCH", path, json=json)

    def delete(self, path: str, json: Any | None = None) -> dict[str, Any]:
        return self._request_with_retry("DELETE", path, json=json)

    def api_path(self, path: str) -> str:
        if not path.startswith("/openapi/v1/"):
            return path
        prefix = f"/openapi/v1/{self.omadac_id}/"
        if path.startswith(prefix):
            return path
        suffix = path.removeprefix("/openapi/v1/")
        return f"{prefix}{suffix}"

    def _request_with_retry(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        attempts = self.max_retries + 1 if self.enable_retry else 1
        last_error: OmadaConnectionError | None = None
        for _ in range(attempts):
            try:
                return self._request(method, path, **kwargs)
            except OmadaConnectionError as exc:
                last_error = exc
        if last_error:
            raise last_error
        raise OmadaConnectionError("Request failed")

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = kwargs.pop("headers", {})
        headers.update(self.auth.get_headers())
        self.logger.debug("%s %s", method, path)
        self.logger.debug("headers=%s", mask_sensitive_headers(headers))
        self.logger.debug("json=%s", format_body(kwargs.get("json")))

        try:
            response = self._http.request(method, path, headers=headers, **kwargs)
        except httpx.RequestError as exc:
            raise OmadaConnectionError("Network request failed", original_error=exc) from exc

        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        payload = _parse_payload(response)
        if response.status_code < 400:
            if isinstance(payload, dict):
                return payload
            return {"result": payload}

        message = _extract_message(payload, default=f"HTTP {response.status_code}")
        if response.status_code == 401:
            self.auth.clear_token()
            raise OmadaAuthenticationError(message, status_code=401, response_data=payload)
        if response.status_code == 403:
            raise OmadaPermissionError(message, status_code=403, response_data=payload)
        if response.status_code == 404:
            raise OmadaNotFoundError(message, status_code=404, response_data=payload)
        if response.status_code == 422:
            errors = payload.get("errors", []) if isinstance(payload, dict) else []
            raise OmadaValidationError(
                message,
                status_code=422,
                response_data=payload,
                errors=errors,
            )
        raise OmadaAPIError(message, status_code=response.status_code, response_data=payload)


def _parse_payload(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        text = response.text
        if not text:
            return {}
        return {"raw": text}


def _extract_message(payload: Any, default: str) -> str:
    if isinstance(payload, dict):
        for key in ("message", "msg", "error", "error_description"):
            if key in payload and payload[key]:
                return str(payload[key])
        result = payload.get("result")
        if isinstance(result, dict):
            for key in ("message", "msg"):
                if key in result and result[key]:
                    return str(result[key])
    return default
