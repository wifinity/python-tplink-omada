"""Omada client exception hierarchy."""

from __future__ import annotations

from typing import Any


class OmadaAPIError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_data: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class OmadaAuthenticationError(OmadaAPIError):
    pass


class OmadaPermissionError(OmadaAPIError):
    pass


class OmadaNotFoundError(OmadaAPIError):
    pass


class DeviceNotFoundError(OmadaNotFoundError):
    pass


class WLANGroupNotFoundError(OmadaNotFoundError):
    pass


class OmadaValidationError(OmadaAPIError):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_data: Any = None,
        errors: list[Any] | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, response_data=response_data)
        self.errors = errors or []


class OmadaConnectionError(OmadaAPIError):
    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


class WiFiNetworkPartiallyConfiguredError(OmadaAPIError):
    """An SSID was created but a post-create PATCH step failed.

    The SSID exists on the controller and is partially configured. ``ssid_id`` lets the caller
    retry the failed step or delete the SSID; the underlying error is preserved as ``__cause__``.
    """

    def __init__(
        self,
        *,
        ssid_id: str,
        failed_step: str,
        completed_steps: list[str],
    ) -> None:
        super().__init__(
            f"SSID created (ssidId={ssid_id}) but post-create step '{failed_step}' failed; "
            "SSID exists and is partially configured"
        )
        self.ssid_id = ssid_id
        self.failed_step = failed_step
        self.completed_steps = completed_steps
