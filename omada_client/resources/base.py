"""Shared helper for resource wrappers."""

from __future__ import annotations

from typing import Any


class BaseResource:
    def __init__(self, client: Any, path: str) -> None:
        self.client = client
        self.path = path

    def list(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        payload = self.client.get(self.path, params=params or {})
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            data = payload.get("data") or payload.get("result") or payload.get("items")
            if isinstance(data, list):
                return data
        return []
