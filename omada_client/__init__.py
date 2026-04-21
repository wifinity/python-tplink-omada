"""Public package exports for Omada client."""

from .client import OmadaClient
from .exceptions import (
    OmadaAPIError,
    OmadaAuthenticationError,
    OmadaConnectionError,
    OmadaNotFoundError,
    OmadaPermissionError,
    OmadaValidationError,
)
from .logging_config import set_log_level

__all__ = [
    "OmadaClient",
    "OmadaAPIError",
    "OmadaAuthenticationError",
    "OmadaPermissionError",
    "OmadaNotFoundError",
    "OmadaValidationError",
    "OmadaConnectionError",
    "set_log_level",
]

__version__ = "0.1.0"
