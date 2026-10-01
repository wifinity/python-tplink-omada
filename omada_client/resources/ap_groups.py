"""AP group operations for Omada (controller 6.3+)."""

from __future__ import annotations

from typing import Any, cast

from ..exceptions import APGroupNotFoundError
from ..mac import normalize_mac
from .base import fetch_all_pages


class APGroupsResource:
    """Site-scoped AP groups on ``/sites/{siteId}/ap-groups``.

    An AP group is the set of APs that broadcast the SSIDs bound to it. SSIDs are bound to
    AP groups from the SSID side (``wifi_networks.set_ap_groups``).
    """

    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    @staticmethod
    def _extract_id(item: dict[str, Any]) -> str | None:
        value = item.get("id")
        if isinstance(value, str) and value:
            return value
        return None

    @staticmethod
    def _require_one_selector(id: str | None, name: str | None) -> None:
        if (id is None) == (name is None):
            raise ValueError("Provide exactly one of 'id' or 'name'")

    @staticmethod
    def _normalize_macs(macs: list[str] | None, *, field: str) -> list[str]:
        if macs is None:
            return []
        if not isinstance(macs, list):
            raise ValueError(f"{field} must be a list of MAC addresses")
        return [normalize_mac(mac) for mac in macs]

    def _resolve_by_name(self, *, site_id: str, name: str) -> dict[str, Any]:
        groups = self.all(site_id=site_id, search_key=name)
        matches = [group for group in groups if group.get("name") == name]
        if not matches:
            raise APGroupNotFoundError(f"AP group with name '{name}' was not found")
        if len(matches) > 1:
            raise ValueError(f"Multiple AP groups found with name '{name}'")
        return matches[0]

    def _resolve_id(self, *, site_id: str, id: str | None, name: str | None) -> str:
        self._require_one_selector(id, name)
        if id is not None:
            return id
        group_id = self._extract_id(self._resolve_by_name(site_id=site_id, name=cast(str, name)))
        if group_id is None:
            raise ValueError(f"Matched AP group '{name}' does not include a valid id")
        return group_id

    def resolve_ids(self, *, site_id: str, ap_groups: list[str]) -> list[str]:
        """Map AP group ids or names to ids with one list call.

        Each entry matches a group ``id`` first, then an exact ``name``. Unknown entries raise
        ``APGroupNotFoundError``; a name shared by several groups raises ``ValueError``.
        """
        if not isinstance(ap_groups, list) or not ap_groups:
            raise ValueError("ap_groups must be a non-empty list of AP group ids or names")
        if not all(isinstance(entry, str) and entry for entry in ap_groups):
            raise ValueError("ap_groups entries must be non-empty strings")
        groups = self.all(site_id=site_id)
        resolved: list[str] = []
        for entry in ap_groups:
            by_id = [group for group in groups if self._extract_id(group) == entry]
            matches = by_id or [group for group in groups if group.get("name") == entry]
            if not matches:
                raise APGroupNotFoundError(f"AP group '{entry}' was not found on site '{site_id}'")
            if len(matches) > 1:
                raise ValueError(f"Multiple AP groups found with name '{entry}'")
            group_id = self._extract_id(matches[0])
            if group_id is None:
                raise ValueError(f"Matched AP group '{entry}' does not include a valid id")
            if group_id not in resolved:
                resolved.append(group_id)
        return resolved

    def all(self, *, site_id: str, search_key: str | None = None) -> list[dict[str, Any]]:
        params = {"searchKey": search_key} if search_key else None
        return fetch_all_pages(self.client, self._path(f"/openapi/v1/sites/{site_id}/ap-groups"), params=params)

    def get(self, *, site_id: str, id: str | None = None, name: str | None = None) -> dict[str, Any]:
        self._require_one_selector(id, name)
        if name is not None:
            return self._resolve_by_name(site_id=site_id, name=name)
        response = cast(
            dict[str, Any],
            self.client.get(self._path(f"/openapi/v1/sites/{site_id}/ap-groups/{id}/info")),
        )
        result = response.get("result")
        if not isinstance(result, dict) or not result:
            raise APGroupNotFoundError(f"AP group with id '{id}' was not found")
        return result

    def create(self, *, site_id: str, name: str, ap_macs: list[str] | None = None) -> dict[str, Any]:
        """Create an AP group; the new id is at ``result.id``."""
        if not isinstance(name, str) or not name:
            raise ValueError("name must be a non-empty string")
        payload: dict[str, Any] = {"name": name}
        if ap_macs is not None:
            payload["apMacs"] = self._normalize_macs(ap_macs, field="ap_macs")
        response = self.client.post(self._path(f"/openapi/v1/sites/{site_id}/ap-groups"), json=payload)
        return cast(dict[str, Any], response)

    def update(
        self,
        *,
        site_id: str,
        id: str | None = None,
        name: str | None = None,
        new_name: str | None = None,
        add_ap_macs: list[str] | None = None,
        remove_ap_macs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Rename an AP group and/or move APs in or out of it.

        The controller requires ``name`` on every PATCH, so the current name is sent when
        ``new_name`` is not given.
        """
        self._require_one_selector(id, name)
        if new_name is None and add_ap_macs is None and remove_ap_macs is None:
            raise ValueError("Provide at least one of new_name, add_ap_macs or remove_ap_macs")
        if new_name is not None and (not isinstance(new_name, str) or not new_name):
            raise ValueError("new_name must be a non-empty string when provided")

        if name is not None:
            group = self._resolve_by_name(site_id=site_id, name=name)
        else:
            group = self.get(site_id=site_id, id=id)
        group_id = self._extract_id(group) or id
        if group_id is None:
            raise ValueError(f"Matched AP group '{name}' does not include a valid id")
        current_name = group.get("name")

        payload: dict[str, Any] = {"name": new_name if new_name is not None else current_name}
        if not isinstance(payload["name"], str) or not payload["name"]:
            raise ValueError(f"AP group '{group_id}' has no name; pass new_name")
        if add_ap_macs is not None:
            payload["addApMacs"] = self._normalize_macs(add_ap_macs, field="add_ap_macs")
        if remove_ap_macs is not None:
            payload["removeApMacs"] = self._normalize_macs(remove_ap_macs, field="remove_ap_macs")

        response = self.client.patch(self._path(f"/openapi/v1/sites/{site_id}/ap-groups/{group_id}"), json=payload)
        return cast(dict[str, Any], response)

    def delete(self, *, site_id: str, id: str | None = None, name: str | None = None) -> dict[str, Any]:
        group_id = self._resolve_id(site_id=site_id, id=id, name=name)
        response = self.client.delete(self._path(f"/openapi/v1/sites/{site_id}/ap-groups/{group_id}"))
        return cast(dict[str, Any], response)
