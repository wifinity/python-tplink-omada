"""Switch operations implemented as a typed facade over devices."""

from __future__ import annotations

from typing import Any, Dict, List, cast

from ..exceptions import DeviceNotFoundError
from ..mac import normalize_mac
from .devices import augment_device_status_meanings


class SwitchesResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def all(
        self,
        *,
        site_id: str,
        page: int = 1,
        page_size: int = 1000,
        **params: Any,
    ) -> dict[str, Any]:
        return cast(
            Dict[str, Any],
            self.client.devices.list(
                site_id=site_id,
                page=page,
                page_size=page_size,
                deviceType="switch",
                **params,
            ),
        )

    def get_by_mac(self, *, site_id: str, mac: str) -> dict[str, Any]:
        normalized_mac = normalize_mac(mac)
        response = cast(
            Dict[str, Any],
            self.client.devices.list(site_id=site_id, searchKey=normalized_mac, deviceType="switch"),
        )
        items = self._extract_items(response)
        for item in items:
            if not isinstance(item, dict):
                continue
            if self._matches_mac(item.get("mac"), normalized_mac):
                matched = cast(Dict[str, Any], item)
                augment_device_status_meanings(matched)
                return matched
        raise DeviceNotFoundError(f"Switch with MAC '{mac}' not found in site '{site_id}'")

    def get_by_name(self, *, site_id: str, name: str) -> dict[str, Any]:
        response = cast(
            Dict[str, Any],
            self.client.devices.list(site_id=site_id, searchKey=name, deviceType="switch"),
        )
        items = self._extract_items(response)
        exact_matches: List[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("name") == name:
                matched = cast(Dict[str, Any], item)
                augment_device_status_meanings(matched)
                exact_matches.append(matched)
        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(exact_matches) > 1:
            raise ValueError(f"Multiple switches named '{name}' found in site '{site_id}'")
        raise ValueError(f"Switch named '{name}' not found in site '{site_id}'")

    def create(
        self,
        *,
        site_id: str,
        device_key: str,
        name: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        return cast(
            Dict[str, Any],
            self.client.devices.add_by_device_key(
                site_id=site_id,
                device_key=device_key,
                name=name,
                username=username,
                password=password,
            ),
        )

    def start_adopt(
        self,
        *,
        site_id: str,
        mac: str,
        username: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        return cast(
            Dict[str, Any],
            self.client.devices.start_adopt(site_id=site_id, mac=mac, username=username, password=password),
        )

    def check_adopt(self, *, site_id: str, mac: str) -> dict[str, Any]:
        return cast(Dict[str, Any], self.client.devices.check_adopt(site_id=site_id, mac=mac))

    def get_ports(self, *, site_id: str, switch_mac: str) -> list[dict[str, Any]]:
        """Return current port settings for one switch.

        Uses POST /switches/ports/select with selectAll=true filtered to this switch MAC.
        Each item in the returned list is an OswPortVO with fields including
        'port' (int), 'name' (str), and 'disable' (bool).
        Returns [] when the switch is not present in the response.
        """
        normalized = normalize_mac(switch_mac)
        response = cast(
            Dict[str, Any],
            self.client.post(
                self.client.api_path(f"/openapi/v1/sites/{site_id}/switches/ports/select"),
                json={"selectAll": True, "switchList": [], "filters": {"switchMac": normalized}},
            ),
        )
        all_switches = self._extract_items(response)
        for sw in all_switches:
            if not isinstance(sw, dict):
                continue
            if self._matches_mac(sw.get("mac"), normalized):
                ports = sw.get("ports") or []
                return list(ports) if isinstance(ports, list) else []
        return []

    def set_ports_name(
        self,
        *,
        site_id: str,
        switch_mac: str,
        port_names: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Rename multiple ports in one request.

        port_names: list of {port: int, name: str}
        PUT /switches/{switchMac}/multi-ports/name
        """
        normalized = normalize_mac(switch_mac)
        return cast(
            Dict[str, Any],
            self.client.put(
                self.client.api_path(f"/openapi/v1/sites/{site_id}/switches/{normalized}/multi-ports/name"),
                json={"portNameList": port_names},
            ),
        )

    def set_ports_status(
        self,
        *,
        site_id: str,
        switch_mac: str,
        port_list: list[int],
        enabled: bool,
    ) -> dict[str, Any]:
        """Enable or disable a list of ports in one request.

        PATCH /switches/{switchMac}/multi-ports/config (BatchOswPortSettingVO.disable)
        """
        normalized = normalize_mac(switch_mac)
        return cast(
            Dict[str, Any],
            self.client.patch(
                self.client.api_path(f"/openapi/v1/sites/{site_id}/switches/{normalized}/multi-ports/config"),
                json={"portList": port_list, "disable": not enabled},
            ),
        )

    def delete(self, *, site_id: str, mac: str) -> dict[str, Any]:
        normalized_mac = normalize_mac(mac)
        return cast(Dict[str, Any], self.client.devices.delete(site_id=site_id, mac=normalized_mac))

    @staticmethod
    def _extract_items(response: dict[str, Any]) -> List[Any]:
        for key in ("data", "result", "items", "list"):
            value = response.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                for nested_key in ("data", "items", "list"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, list):
                        return nested_value
        return []

    @staticmethod
    def _matches_mac(value: Any, normalized_mac: str) -> bool:
        if not isinstance(value, str):
            return False
        try:
            return normalize_mac(value) == normalized_mac
        except ValueError:
            return False
