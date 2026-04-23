"""AP operations implemented as a typed facade over devices."""

from __future__ import annotations

from typing import Any, List, cast

from ..mac import normalize_mac
from ..exceptions import DeviceNotFoundError
from .devices import augment_device_status_meanings

_AP_WIRED_UPLINK_PORT_TYPE_MEANINGS: dict[int, str] = {
    0: "ETH",
    1: "POTS",
    2: "SFP",
}

_AP_WIRED_UPLINK_LINK_STATUS_MEANINGS: dict[int, str] = {
    0: "Down",
    1: "Up",
}

_AP_WIRED_UPLINK_LINK_SPEED_MEANINGS: dict[int, str] = {
    0: "Auto",
    1: "10M",
    2: "100M",
    3: "1000M",
    4: "2500M",
    5: "10G",
    6: "5G",
    7: "25G",
    8: "100G",
}

_AP_WIRED_UPLINK_DUPLEX_MEANINGS: dict[int, str] = {
    0: "LAN disconnected",
    1: "Half",
    2: "Full",
}


class APsResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    def all(
        self,
        *,
        site_id: str,
        page: int = 1,
        page_size: int = 1000,
        **params: Any,
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            self.client.devices.list(site_id=site_id, page=page, page_size=page_size, deviceType="ap", **params),
        )

    def get_by_mac(self, *, site_id: str, mac: str) -> dict[str, Any]:
        normalized_mac = normalize_mac(mac)
        response = cast(
            dict[str, Any],
            self.client.devices.list(site_id=site_id, searchKey=normalized_mac, deviceType="ap"),
        )
        items = self._extract_items(response)
        for item in items:
            if not isinstance(item, dict):
                continue
            if self._matches_mac(item.get("mac"), normalized_mac):
                matched = cast(dict[str, Any], item)
                augment_device_status_meanings(matched)
                return matched
        raise DeviceNotFoundError(f"AP with MAC '{mac}' not found in site '{site_id}'")

    def get_by_name(self, *, site_id: str, name: str) -> dict[str, Any]:
        response = cast(
            dict[str, Any],
            self.client.devices.list(site_id=site_id, searchKey=name, deviceType="ap"),
        )
        items = self._extract_items(response)
        exact_matches: List[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("name") == name:
                matched = cast(dict[str, Any], item)
                augment_device_status_meanings(matched)
                exact_matches.append(matched)
        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(exact_matches) > 1:
            raise ValueError(f"Multiple APs named '{name}' found in site '{site_id}'")
        raise ValueError(f"AP named '{name}' not found in site '{site_id}'")

    def get_overview_by_mac(self, *, site_id: str, mac: str) -> dict[str, Any]:
        normalized_mac = normalize_mac(mac)
        return cast(dict[str, Any], self.client.get(self._path(f"/openapi/v1/sites/{site_id}/aps/{normalized_mac}")))

    def get_wired_uplink_by_mac(self, *, site_id: str, mac: str) -> dict[str, Any]:
        normalized_mac = normalize_mac(mac)
        response = cast(
            dict[str, Any],
            self.client.get(self._path(f"/openapi/v1/sites/{site_id}/aps/{normalized_mac}/wired-uplink")),
        )
        self._augment_wired_uplink_meanings(response)
        return response

    def create(self, *, site_id: str, device_key: str) -> dict[str, Any]:
        return cast(dict[str, Any], self.client.devices.add_by_device_key(site_id=site_id, device_key=device_key))

    def start_adopt(
        self,
        *,
        site_id: str,
        mac: str,
        username: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            self.client.devices.start_adopt(site_id=site_id, mac=mac, username=username, password=password),
        )

    def check_adopt(self, *, site_id: str, mac: str) -> dict[str, Any]:
        return cast(dict[str, Any], self.client.devices.check_adopt(site_id=site_id, mac=mac))

    def delete(self, *, site_id: str, mac: str) -> dict[str, Any]:
        normalized_mac = normalize_mac(mac)
        return cast(dict[str, Any], self.client.devices.delete(site_id=site_id, mac=normalized_mac))

    def update(self, *, site_id: str, mac: str, data: dict[str, Any]) -> dict[str, Any]:
        normalized_mac = normalize_mac(mac)
        return cast(
            dict[str, Any],
            self.client.patch(
                self._path(f"/openapi/v1/sites/{site_id}/aps/{normalized_mac}/general-config"),
                json=data,
            ),
        )

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

    @staticmethod
    def _augment_wired_uplink_meanings(response: dict[str, Any]) -> None:
        result = response.get("result")
        if not isinstance(result, dict):
            return
        wired_uplink = result.get("wiredUplink")
        if not isinstance(wired_uplink, dict):
            return

        APsResource._assign_meaning(
            payload=wired_uplink,
            code_field="portType",
            meaning_field="portTypeMeaning",
            meanings=_AP_WIRED_UPLINK_PORT_TYPE_MEANINGS,
        )
        APsResource._assign_meaning(
            payload=wired_uplink,
            code_field="linkStatus",
            meaning_field="linkStatusMeaning",
            meanings=_AP_WIRED_UPLINK_LINK_STATUS_MEANINGS,
        )
        APsResource._assign_meaning(
            payload=wired_uplink,
            code_field="linkSpeed",
            meaning_field="linkSpeedMeaning",
            meanings=_AP_WIRED_UPLINK_LINK_SPEED_MEANINGS,
        )
        APsResource._assign_meaning(
            payload=wired_uplink,
            code_field="duplex",
            meaning_field="duplexMeaning",
            meanings=_AP_WIRED_UPLINK_DUPLEX_MEANINGS,
        )

    @staticmethod
    def _assign_meaning(
        *,
        payload: dict[str, Any],
        code_field: str,
        meaning_field: str,
        meanings: dict[int, str],
    ) -> None:
        value = payload.get(code_field)
        if isinstance(value, int):
            payload[meaning_field] = meanings.get(value, f"Unknown {code_field}: {value}")
