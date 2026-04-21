"""AP group operations for Omada."""

from __future__ import annotations

from typing import Any, cast


class APGroupsResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    def create(self, site_id: str, group_data: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(self._path(f"/openapi/v1/sites/{site_id}/ap-groups"), json=group_data)
        return cast(dict[str, Any], response)
