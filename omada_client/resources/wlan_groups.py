"""WLAN group operations for Omada."""

from __future__ import annotations

from typing import Any, cast

from ..exceptions import WLANGroupNotFoundError


class WLANGroupsResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    @staticmethod
    def _coerce_list_response(response: dict[str, Any]) -> list[dict[str, Any]]:
        result = response.get("result")
        if isinstance(result, dict):
            data = result.get("data")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]

        for key in ("data", "items", "result"):
            value = response.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _extract_wlan_group_id(item: dict[str, Any]) -> str | None:
        for key in ("wlanId", "id"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def _resolve_by_name(self, *, site_id: str, name: str) -> dict[str, Any]:
        groups = self.all(site_id=site_id, params={"searchKey": name})
        exact_matches = [group for group in groups if isinstance(group.get("name"), str) and group["name"] == name]
        if not exact_matches:
            raise WLANGroupNotFoundError(f"WLAN group with name '{name}' was not found")
        if len(exact_matches) > 1:
            raise ValueError(f"Multiple WLAN groups found with name '{name}'")
        return exact_matches[0]

    def all(self, *, site_id: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        response = self.client.get(
            self._path(f"/openapi/v1/sites/{site_id}/wireless-network/wlans"),
            params=params,
        )
        return self._coerce_list_response(cast(dict[str, Any], response))

    def create(
        self,
        *,
        site_id: str,
        name: str | None = None,
        group_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = dict(group_data) if group_data else {}
        if name is not None:
            payload["name"] = name
        payload.setdefault("clone", False)
        if not isinstance(payload.get("name"), str) or not payload["name"]:
            raise ValueError("name is required; provide name or include a non-empty 'name' in group_data")
        response = self.client.post(
            self._path(f"/openapi/v1/sites/{site_id}/wireless-network/wlans"),
            json=payload,
        )
        return cast(dict[str, Any], response)

    def get(self, *, site_id: str, id: str | None = None, name: str | None = None) -> dict[str, Any]:
        if (id is None) == (name is None):
            raise ValueError("Provide exactly one of 'id' or 'name'")
        if id is not None:
            response = self.client.get(self._path(f"/openapi/v1/sites/{site_id}/wireless-network/wlans/{id}"))
            payload = cast(dict[str, Any], response)
            result = payload.get("result")
            if isinstance(result, dict):
                return result
            return payload
        return self._resolve_by_name(site_id=site_id, name=cast(str, name))

    def delete(self, *, site_id: str, id: str | None = None, name: str | None = None) -> dict[str, Any]:
        if (id is None) == (name is None):
            raise ValueError("Provide exactly one of 'id' or 'name'")
        wlan_id = id
        if wlan_id is None:
            group = self._resolve_by_name(site_id=site_id, name=cast(str, name))
            wlan_id = self._extract_wlan_group_id(group)
            if wlan_id is None:
                raise ValueError(f"Matched WLAN group '{name}' does not include a valid wlanId")
        response = self.client.delete(self._path(f"/openapi/v1/sites/{site_id}/wireless-network/wlans/{wlan_id}"))
        return cast(dict[str, Any], response)
