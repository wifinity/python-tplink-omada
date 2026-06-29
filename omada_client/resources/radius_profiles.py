"""RADIUS profile operations for Omada."""

from __future__ import annotations

from typing import Any, Dict, cast


class RadiusProfilesResource:
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
    def _extract_profile_id(item: dict[str, Any]) -> str | None:
        value = item.get("radiusProfileId")
        if isinstance(value, str) and value:
            return value
        return None

    def all(self, *, site_id: str) -> list[dict[str, Any]]:
        response = self.client.get(
            self._path(f"/openapi/v1/sites/{site_id}/profiles/radius"),
        )
        return self._coerce_list_response(cast(Dict[str, Any], response))

    def get(self, *, site_id: str, id: str | None = None, name: str | None = None) -> dict[str, Any]:
        from ..exceptions import RadiusProfileNotFoundError

        if (id is None) == (name is None):
            raise ValueError("Provide exactly one of 'id' or 'name'")
        profiles = self.all(site_id=site_id)
        if id is not None:
            for item in profiles:
                if self._extract_profile_id(item) == id:
                    return item
            raise RadiusProfileNotFoundError(f"RADIUS profile with id '{id}' was not found")
        exact = [item for item in profiles if item.get("name") == name]
        if not exact:
            raise RadiusProfileNotFoundError(f"RADIUS profile with name '{name}' was not found")
        if len(exact) > 1:
            raise ValueError(f"Multiple RADIUS profiles found with name '{name}'")
        return exact[0]

    def create(
        self,
        *,
        site_id: str,
        name: str,
        auth_servers: list[dict[str, Any]],
        accounting_enabled: bool = False,
        wireless_vlan_assignment: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not isinstance(name, str) or not name:
            raise ValueError("name must be a non-empty string")
        if not auth_servers:
            raise ValueError("auth_servers must be a non-empty list")
        payload: dict[str, Any] = {
            "name": name,
            "authServer": auth_servers,
            "radiusAccountingEnable": accounting_enabled,
            "wirelessVlanAssignment": wireless_vlan_assignment,
        }
        payload.update(kwargs)
        response = self.client.post(
            self._path(f"/openapi/v1/sites/{site_id}/profiles/radius"),
            json=payload,
        )
        return cast(Dict[str, Any], response)

    def upsert(
        self,
        *,
        site_id: str,
        name: str,
        auth_servers: list[dict[str, Any]],
        accounting_enabled: bool = False,
        wireless_vlan_assignment: bool = False,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], bool]:
        """Return (profile_dict, created). Skips creation if a profile with this name already exists.

        Omada error -34015 blocks modification of in-use profiles, so we create-if-absent only.
        """
        profiles = self.all(site_id=site_id)
        existing = [item for item in profiles if item.get("name") == name]
        if existing:
            return existing[0], False
        created = self.create(
            site_id=site_id,
            name=name,
            auth_servers=auth_servers,
            accounting_enabled=accounting_enabled,
            wireless_vlan_assignment=wireless_vlan_assignment,
            **kwargs,
        )
        return created, True
