"""Device operations for Omada workflows."""

from __future__ import annotations

from typing import Any, cast


class DevicesResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    def register(self, site_id: str, device_data: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(self._path(f"/openapi/v1/sites/{site_id}/devices"), json=device_data)
        return cast(dict[str, Any], response)

    def remove(self, site_id: str, device_ids: list[str]) -> dict[str, Any]:
        payload = {"deviceIds": device_ids}
        response = self.client.delete(self._path(f"/openapi/v1/sites/{site_id}/devices"), json=payload)
        return cast(dict[str, Any], response)

    def send_config(self, site_id: str, device_id: str, config: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(
            self._path(f"/openapi/v1/sites/{site_id}/devices/{device_id}/config"),
            json=config,
        )
        return cast(dict[str, Any], response)

    def status(self, site_id: str, device_id: str) -> dict[str, Any]:
        response = self.client.get(self._path(f"/openapi/v1/sites/{site_id}/devices/{device_id}/status"))
        return cast(dict[str, Any], response)
