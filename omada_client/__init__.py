"""Public package exports for Omada client."""

from .client import OmadaClient
from .exceptions import (
    DeviceNotFoundError,
    OmadaAPIError,
    OmadaAuthenticationError,
    OmadaConnectionError,
    OmadaNotFoundError,
    OmadaPermissionError,
    OmadaValidationError,
    WLANGroupNotFoundError,
)
from .logging_config import set_log_level

__all__ = [
    "OmadaClient",
    "DeviceNotFoundError",
    "OmadaAPIError",
    "OmadaAuthenticationError",
    "OmadaPermissionError",
    "OmadaNotFoundError",
    "OmadaValidationError",
    "OmadaConnectionError",
    "WLANGroupNotFoundError",
    "set_log_level",
]

__version__ = "0.1.0"
