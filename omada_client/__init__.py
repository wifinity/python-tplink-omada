"""Public package exports for Omada client."""

from .client import OmadaClient
from .exceptions import (
    APGroupNotFoundError,
    DeviceNotFoundError,
    OmadaAPIError,
    OmadaAuthenticationError,
    OmadaConnectionError,
    OmadaNotFoundError,
    OmadaPermissionError,
    OmadaValidationError,
    RadiusProfileNotFoundError,
    WiFiNetworkNotFoundError,
    WiFiNetworkPartiallyConfiguredError,
)
from .logging_config import set_log_level
from .wifi_payload_utils import (
    ssid_detail_to_basic_config_patch,
    strip_ssid_detail_for_create,
)

__all__ = [
    "OmadaClient",
    "APGroupNotFoundError",
    "DeviceNotFoundError",
    "OmadaAPIError",
    "OmadaAuthenticationError",
    "OmadaPermissionError",
    "OmadaNotFoundError",
    "OmadaValidationError",
    "OmadaConnectionError",
    "RadiusProfileNotFoundError",
    "WiFiNetworkNotFoundError",
    "WiFiNetworkPartiallyConfiguredError",
    "set_log_level",
    "ssid_detail_to_basic_config_patch",
    "strip_ssid_detail_for_create",
]
