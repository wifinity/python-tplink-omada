"""WiFi network operations for Omada."""

from __future__ import annotations

from typing import Any, cast


class WiFiNetworksResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    def create(self, *, site_id: str, network_data: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(self._path(f"/openapi/v1/sites/{site_id}/wlans"), json=network_data)
        return cast(dict[str, Any], response)

    def assign_to_ap_group(
        self,
        *,
        site_id: str,
        wlan_id: str,
        ap_group_id: str,
    ) -> dict[str, Any]:
        payload = {"wlanId": wlan_id, "apGroupId": ap_group_id}
        response = self.client.post(
            self._path(f"/openapi/v1/sites/{site_id}/wlans/{wlan_id}/ap-groups"),
            json=payload,
        )
        return cast(dict[str, Any], response)
