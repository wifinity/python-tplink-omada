"""Logging helpers for request and response tracing."""

from __future__ import annotations

import json
import logging
from typing import Any

LOGGER_NAME = "omada_client"
SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key"}
# Body keys are compared lower-cased with "_" and "-" removed.
SENSITIVE_BODY_KEY_PARTS = ("password", "passwd", "secret", "token", "community")
SENSITIVE_BODY_KEYS = {"pwd", "psk", "radiuspwd", "authkey", "privkey", "privacykey"}


def get_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def set_log_level(level: str) -> None:
    logger = get_logger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))


def mask_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
    masked: dict[str, str] = {}
    for key, value in headers.items():
        masked[key] = "***" if key.lower() in SENSITIVE_HEADERS else value
    return masked


def _is_sensitive_body_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    normalized = key.lower().replace("_", "").replace("-", "")
    return normalized in SENSITIVE_BODY_KEYS or any(part in normalized for part in SENSITIVE_BODY_KEY_PARTS)


def mask_sensitive_body(body: Any) -> Any:
    """Return a copy of ``body`` with credential-like values replaced by ``***`` at any depth."""
    if isinstance(body, dict):
        return {
            key: "***" if _is_sensitive_body_key(key) else mask_sensitive_body(value) for key, value in body.items()
        }
    if isinstance(body, list):
        return [mask_sensitive_body(item) for item in body]
    return body


def format_body(body: Any, max_length: int = 1000) -> str:
    if body is None:
        return ""
    body = mask_sensitive_body(body)
    try:
        rendered = json.dumps(body, sort_keys=True)
    except (TypeError, ValueError):
        rendered = str(body)
    if len(rendered) > max_length:
        return rendered[:max_length] + "...<truncated>"
    return rendered
