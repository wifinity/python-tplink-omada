"""Site-level service settings (SNMP, etc.)."""

from __future__ import annotations

from typing import Any, cast


class SiteServicesResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    def _unwrap_result(self, response: dict[str, Any]) -> dict[str, Any]:
        result = response.get("result")
        if isinstance(result, dict):
            return result
        return response

    def get_snmp(self, *, site_id: str) -> dict[str, Any]:
        response = self.client.get(
            self._path(f"/openapi/v1/sites/{site_id}/setting/service/snmp"),
        )
        return self._unwrap_result(cast(dict[str, Any], response))

    def update_snmp(
        self,
        *,
        site_id: str,
        snmpv1v2c_enable: bool,
        snmpv3_enable: bool,
        community_string: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "snmpV1V2CEnable": snmpv1v2c_enable,
            "snmpV3Enable": snmpv3_enable,
        }
        if community_string is not None:
            payload["communityString"] = community_string
        if username is not None:
            payload["username"] = username
        if password is not None:
            payload["password"] = password
        response = self.client.patch(
            self._path(f"/openapi/v1/sites/{site_id}/setting/service/snmp"),
            json=payload,
        )
        return cast(dict[str, Any], response)
