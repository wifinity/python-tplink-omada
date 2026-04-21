"""Site-related Omada operations."""

from __future__ import annotations

from typing import Any, cast


class SitesResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    def create(self, name: str, tz: str | None = None, **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name, **kwargs}
        if tz:
            payload["tz"] = tz
        response = self.client.post(self._path("/openapi/v1/sites"), json=payload)
        return cast(dict[str, Any], response)
