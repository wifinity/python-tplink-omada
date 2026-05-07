"""OLT / ONU management operations."""

from __future__ import annotations

from typing import Any, Dict, List, cast

from ..mac import normalize_mac


class OLTsResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    def list_onus(
        self,
        *,
        site_id: str,
        olt_mac: str,
        pon_port: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_olt_mac = normalize_mac(olt_mac)
        query: dict[str, Any] = {"ponPort": pon_port}
        if params:
            query.update(params)
        response = self.client.get(
            self._path(f"/openapi/v1/sites/{site_id}/olts/{normalized_olt_mac}/pon/onu-management/informations/list"),
            params=query,
        )
        return cast(Dict[str, Any], response)

    def get_onu_detail(
        self,
        *,
        site_id: str,
        olt_mac: str,
        onu_key: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(onu_key, str) or not onu_key:
            raise ValueError("onu_key must be a non-empty string")
        normalized_olt_mac = normalize_mac(olt_mac)
        query: dict[str, Any] = {"key": onu_key}
        if params:
            query.update(params)
        response = self.client.get(
            self._path(
                f"/openapi/v1/sites/{site_id}/olts/{normalized_olt_mac}/pon/onu-management/informations/detail/get"
            ),
            params=query,
        )
        return cast(Dict[str, Any], response)

    def resolve_onu_key(
        self,
        *,
        site_id: str,
        olt_mac: str,
        pon_port: str,
        onu_mac: str,
    ) -> str:
        normalized_onu_mac = normalize_mac(onu_mac)
        payload = self.list_onus(site_id=site_id, olt_mac=olt_mac, pon_port=pon_port)
        items = self._extract_items(payload)

        for item in items:
            if not isinstance(item, dict):
                continue
            if self._item_matches_onu_mac(item, normalized_onu_mac):
                key = item.get("key")
                if isinstance(key, str) and key:
                    return key
                raise ValueError(f"Matched ONU '{onu_mac}' does not include a valid key")

        raise ValueError(f"ONU with MAC '{onu_mac}' not found on pon_port '{pon_port}' in site '{site_id}'")

    def get_onu_detail_by_mac(
        self,
        *,
        site_id: str,
        olt_mac: str,
        pon_port: str,
        onu_mac: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        onu_key = self.resolve_onu_key(site_id=site_id, olt_mac=olt_mac, pon_port=pon_port, onu_mac=onu_mac)
        return self.get_onu_detail(site_id=site_id, olt_mac=olt_mac, onu_key=onu_key, params=params)

    @staticmethod
    def _extract_items(payload: dict[str, Any]) -> List[Any]:
        for key in ("data", "result", "items", "list"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                for nested_key in ("data", "items", "list"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, list):
                        return nested_value
        return []

    @staticmethod
    def _item_matches_onu_mac(item: dict[str, Any], normalized_onu_mac: str) -> bool:
        for candidate_key in ("mac", "onuMac", "ontMac", "deviceMac", "macAddress"):
            value = item.get(candidate_key)
            if not isinstance(value, str) or not value:
                continue
            try:
                if normalize_mac(value) == normalized_onu_mac:
                    return True
            except ValueError:
                continue
        return False
