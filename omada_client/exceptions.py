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
