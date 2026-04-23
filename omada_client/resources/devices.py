"""Device operations for Omada workflows."""

from __future__ import annotations

from typing import Any, List, cast

from ..mac import normalize_mac

_ADOPT_ERROR_CODE_MEANINGS: dict[int, str] = {
    0: "Adopt Device Success",
    -39002: "Device adoption failed because the device does not respond to adopt commands",
    -39003: "Failed to adopt the Device because the username or password is incorrect",
    -39004: "Failed to adopt device",
    -39005: "Failed to adopt this device because the device is not connected",
    -39329: "Failed to link to the uplink AP",
}

_ADOPT_FAILED_TYPE_MEANINGS: dict[int, str] = {
    -1: "No need print username or password",
    -2: "Need print username or password",
}

_DEVICE_STATUS_MEANINGS: dict[int, str] = {
    0: "Disconnected",
    1: "Connected",
    2: "Pending",
    3: "Heartbeat Missed",
    4: "Isolated",
}

_DEVICE_DETAIL_STATUS_MEANINGS: dict[int, str] = {
    0: "Disconnected",
    1: "Disconnected(Migrating)",
    10: "Provisioning",
    11: "Configuring",
    12: "Upgrading",
    13: "Rebooting",
    14: "Connected",
    15: "Connected(Wireless)",
    16: "Connected(Migrating)",
    17: "Connected(Wireless,Migrating)",
    20: "Pending",
    21: "Pending(Wireless)",
    22: "Adopting",
    23: "Adopting(Wireless)",
    24: "Adopt Failed",
    25: "Adopt Failed(Wireless)",
    26: "Managed By Others",
    27: "Managed By Others(Wireless)",
    30: "Heartbeat Missed",
    31: "Heartbeat Missed(Wireless)",
    32: "Heartbeat Missed(Migrating)",
    33: "Heartbeat Missed(Wireless,Migrating)",
    40: "Isolated",
    41: "Isolated(Migrating)",
    50: "Slice Configuring",
}


class DevicesResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    def list(
        self,
        *,
        site_id: str,
        page: int = 1,
        page_size: int = 1000,
        **params: Any,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"page": page, "pageSize": page_size}
        query.update(params)
        response = self.client.get(self._path(f"/openapi/v1/sites/{site_id}/devices"), params=query)
        return cast(dict[str, Any], response)

    def get_by_mac(
        self,
        *,
        site_id: str,
        mac: str,
        device_type: str | None = None,
    ) -> dict[str, Any]:
        normalized_mac = normalize_mac(mac)

        if (device_type or "").lower() == "ap":
            response = self.client.get(self._path(f"/openapi/v1/sites/{site_id}/aps/{normalized_mac}"))
            return cast(dict[str, Any], response)

        response = self.list(site_id=site_id, searchKey=normalized_mac)
        items = self._extract_device_items(response)
        for item in items:
            if not isinstance(item, dict):
                continue
            values = [
                item.get("mac"),
                item.get("deviceMac"),
                item.get("macAddress"),
            ]
            if any(_matches_mac(value, normalized_mac) for value in values):
                matched = cast(dict[str, Any], item)
                augment_device_status_meanings(matched)
                return matched

        raise ValueError(f"Device with MAC '{mac}' not found in site '{site_id}'")

    def create(self, *, site_id: str, device_data: dict[str, Any]) -> dict[str, Any]:
        return self.register(site_id=site_id, device_data=device_data)

    def start_adopt(
        self,
        *,
        site_id: str,
        mac: str,
        username: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        normalized_mac = normalize_mac(mac)
        payload = {
            "username": username if username is not None else "admin",
            "password": password if password is not None else "admin",
        }
        response = self.client.post(
            self._path(f"/openapi/v1/sites/{site_id}/devices/{normalized_mac}/start-adopt"),
            json=payload,
        )
        return cast(dict[str, Any], response)

    def check_adopt(self, *, site_id: str, mac: str) -> dict[str, Any]:
        normalized_mac = normalize_mac(mac)
        response = cast(
            dict[str, Any],
            self.client.get(self._path(f"/openapi/v1/sites/{site_id}/devices/{normalized_mac}/adopt-result")),
        )
        result = response.get("result")
        if isinstance(result, dict):
            self._augment_adopt_result_meanings(result)
        return response

    def add_by_device_key(
        self,
        *,
        site_id: str,
        device_key: str,
        name: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        device: dict[str, Any] = {"deviceKey": device_key}
        if name is not None:
            device["name"] = name
        if username is not None:
            device["username"] = username
        if password is not None:
            device["password"] = password
        payload = {"devices": [device]}
        response = self.client.post(
            self._path(f"/openapi/v1/sites/{site_id}/multi-devices/devicekey-add"), json=payload
        )
        return cast(dict[str, Any], response)

    def delete(self, *, site_id: str, mac: str) -> dict[str, Any]:
        normalized_mac = normalize_mac(mac)
        response = self.client.post(self._path(f"/openapi/v1/sites/{site_id}/devices/{normalized_mac}/forget"))
        return cast(dict[str, Any], response)

    def register(self, *, site_id: str, device_data: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(self._path(f"/openapi/v1/sites/{site_id}/devices"), json=device_data)
        return cast(dict[str, Any], response)

    def remove(self, *, site_id: str, device_ids: List[str]) -> dict[str, Any]:
        payload = {"deviceIds": device_ids}
        response = self.client.delete(self._path(f"/openapi/v1/sites/{site_id}/devices"), json=payload)
        return cast(dict[str, Any], response)

    def send_config(self, *, site_id: str, device_id: str, config: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(
            self._path(f"/openapi/v1/sites/{site_id}/devices/{device_id}/config"),
            json=config,
        )
        return cast(dict[str, Any], response)

    def status(self, *, site_id: str, device_id: str) -> dict[str, Any]:
        response = self.client.get(self._path(f"/openapi/v1/sites/{site_id}/devices/{device_id}/status"))
        return cast(dict[str, Any], response)

    @staticmethod
    def _extract_device_items(response: dict[str, Any]) -> List[Any]:
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
    def _augment_adopt_result_meanings(result: dict[str, Any]) -> None:
        adopt_error_code = result.get("adoptErrorCode")
        if isinstance(adopt_error_code, int):
            result["adoptErrorMeaning"] = _ADOPT_ERROR_CODE_MEANINGS.get(
                adopt_error_code,
                f"Unknown adoptErrorCode: {adopt_error_code}",
            )

        adopt_failed_type = result.get("adoptFailedType")
        if isinstance(adopt_failed_type, int):
            result["adoptFailedTypeMeaning"] = _ADOPT_FAILED_TYPE_MEANINGS.get(
                adopt_failed_type,
                f"Unknown adoptFailedType: {adopt_failed_type}",
            )


def augment_device_status_meanings(device_info: dict[str, Any]) -> None:
    status = device_info.get("status")
    if isinstance(status, int):
        device_info["statusMeaning"] = _DEVICE_STATUS_MEANINGS.get(status, f"Unknown status: {status}")

    detail_status = device_info.get("detailStatus")
    if isinstance(detail_status, int):
        device_info["detailStatusMeaning"] = _DEVICE_DETAIL_STATUS_MEANINGS.get(
            detail_status,
            f"Unknown detailStatus: {detail_status}",
        )


def _matches_mac(value: Any, normalized_mac: str) -> bool:
    if not isinstance(value, str):
        return False

    try:
        return normalize_mac(value) == normalized_mac
    except ValueError:
        return False
