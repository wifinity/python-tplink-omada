"""Logging helpers for request and response tracing."""

from __future__ import annotations

import json
import logging
from typing import Any

LOGGER_NAME = "omada_client"
SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key"}


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


def format_body(body: Any, max_length: int = 1000) -> str:
    if body is None:
        return ""
    try:
        rendered = json.dumps(body, sort_keys=True)
    except (TypeError, ValueError):
        rendered = str(body)
    if len(rendered) > max_length:
        return rendered[:max_length] + "...<truncated>"
    return rendered
