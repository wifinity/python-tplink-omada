"""WiFi network operations for Omada."""

from __future__ import annotations

from typing import Any, cast

_SUPPORTED_WIFI_TYPES = ("open", "aaa", "psk", "dpsk")
_TYPE_TO_SECURITY = {
    "open": 0,
    "aaa": 2,
    "psk": 3,
    "dpsk": 5,
}


class WiFiNetworksResource:
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
    def _extract_wlan_id(item: dict[str, Any]) -> str | None:
        for key in ("wlanId", "id"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _extract_ssid_id(item: dict[str, Any]) -> str | None:
        for key in ("ssidId", "id"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _validate_type(network_type: str) -> None:
        if network_type in {"guest", "hotspot20"}:
            raise ValueError(
                "Unsupported Wi-Fi type " f"'{network_type}'. Supported types are: {', '.join(_SUPPORTED_WIFI_TYPES)}"
            )
        if network_type not in _SUPPORTED_WIFI_TYPES:
            raise ValueError(
                f"Invalid Wi-Fi type '{network_type}'. Supported types are: {', '.join(_SUPPORTED_WIFI_TYPES)}"
            )

    @staticmethod
    def _normalize_network_type(raw_type: Any) -> str:
        network_type = raw_type.strip().lower() if isinstance(raw_type, str) else raw_type
        if not isinstance(network_type, str) or not network_type:
            raise ValueError("type must be a non-empty string")
        return network_type

    @staticmethod
    def _validate_ssid_inputs(*, ssid: Any, network_data: dict[str, Any] | None, kwargs: dict[str, Any]) -> None:
        if not isinstance(ssid, str) or not ssid:
            raise ValueError("ssid must be a non-empty string")
        if "name" in kwargs:
            raise ValueError("name is not accepted; set ssid only")
        if network_data is not None and "name" in network_data:
            raise ValueError("network_data must not include 'name'; set ssid only")

    @staticmethod
    def _build_default_create_payload(*, ssid: str, network_type: str) -> dict[str, Any]:
        return {
            "band": 3,
            "broadcast": True,
            "deviceType": 1,
            "enable11r": False,
            "guestNetEnable": False,
            "hidePwd": False,
            "mloEnable": False,
            "name": ssid,
            "pmfMode": 2,
            "security": _TYPE_TO_SECURITY[network_type],
            "vlanEnable": False,
        }

    @staticmethod
    def _apply_psk_settings(*, payload: dict[str, Any], kwargs: dict[str, Any]) -> None:
        psk = kwargs.pop("psk", None)
        psk_setting = kwargs.pop("psk_setting", None)
        if psk_setting is not None and not isinstance(psk_setting, dict):
            raise ValueError("psk_setting must be a dict when provided")
        if psk is not None:
            if not isinstance(psk, str) or not psk:
                raise ValueError("psk must be a non-empty string")
            payload["pskSetting"] = {
                "securityKey": psk,
                "versionPsk": 2,
                "encryptionPsk": 3,
                "gikRekeyPskEnable": False,
            }
            return
        if isinstance(psk_setting, dict):
            payload["pskSetting"] = dict(psk_setting)

    @staticmethod
    def _apply_dpsk_settings(*, payload: dict[str, Any], kwargs: dict[str, Any]) -> None:
        ppsk_setting = kwargs.pop("ppsk_setting", None)
        if ppsk_setting is not None and not isinstance(ppsk_setting, dict):
            raise ValueError("ppsk_setting must be a dict when provided")
        if isinstance(ppsk_setting, dict):
            payload["ppskSetting"] = dict(ppsk_setting)

    @staticmethod
    def _apply_aaa_settings(*, payload: dict[str, Any], kwargs: dict[str, Any]) -> None:
        ent_setting = kwargs.pop("ent_setting", None)
        if ent_setting is not None and not isinstance(ent_setting, dict):
            raise ValueError("ent_setting must be a dict when provided")
        if isinstance(ent_setting, dict):
            payload["entSetting"] = dict(ent_setting)

    def _apply_type_specific_settings(
        self, *, payload: dict[str, Any], network_type: str, kwargs: dict[str, Any]
    ) -> None:
        if network_type == "psk":
            self._apply_psk_settings(payload=payload, kwargs=kwargs)
        if network_type == "dpsk":
            self._apply_dpsk_settings(payload=payload, kwargs=kwargs)
        if network_type == "aaa":
            self._apply_aaa_settings(payload=payload, kwargs=kwargs)

    @staticmethod
    def _apply_vlan_setting(*, payload: dict[str, Any], kwargs: dict[str, Any]) -> None:
        vlan = kwargs.pop("vlan", None)
        if vlan is None:
            return
        if not isinstance(vlan, int) or not (1 <= vlan <= 4094):
            raise ValueError("vlan must be an integer in range 1..4094")
        payload["vlanEnable"] = True
        payload["vlanId"] = vlan

    @staticmethod
    def _validate_required_payload_fields(payload: dict[str, Any]) -> None:
        required_fields = (
            "band",
            "broadcast",
            "deviceType",
            "enable11r",
            "guestNetEnable",
            "hidePwd",
            "mloEnable",
            "name",
            "pmfMode",
            "security",
            "vlanEnable",
        )
        missing = [field for field in required_fields if field not in payload]
        if missing:
            raise ValueError(f"Missing required SSID fields in payload: {', '.join(missing)}")

    @staticmethod
    def _validate_security_type_requirements(*, network_type: str, payload: dict[str, Any]) -> None:
        if network_type == "psk" and not isinstance(payload.get("pskSetting"), dict):
            raise ValueError("type='psk' requires psk_setting (dict) or psk (string)")
        if network_type == "dpsk" and not isinstance(payload.get("ppskSetting"), dict):
            raise ValueError("type='dpsk' requires ppsk_setting (dict)")
        if network_type == "aaa" and not isinstance(payload.get("entSetting"), dict):
            raise ValueError("type='aaa' requires ent_setting (dict)")

    def _resolve_wlan_group_id(self, *, site_id: str, wlan_group: str) -> str:
        if not isinstance(wlan_group, str) or not wlan_group:
            raise ValueError("wlan_group must be a non-empty string")

        if not hasattr(self.client, "wlan_groups"):
            raise ValueError("client.wlan_groups is required to resolve wlan_group")

        group_by_id_getter = getattr(self.client.wlan_groups, "get", None)
        if not callable(group_by_id_getter):
            raise ValueError("client.wlan_groups.get is required to resolve wlan_group")

        try:
            by_id = cast(dict[str, Any], group_by_id_getter(site_id=site_id, id=wlan_group))
            by_id_wlan_id = self._extract_wlan_id(by_id)
            if by_id_wlan_id is not None:
                return by_id_wlan_id
            # Some controllers return minimal/empty detail payloads; if id lookup itself
            # succeeded, treat the caller input as the resolved wlan id.
            return wlan_group
        except Exception:
            # Fall back to name-based resolution when id lookup fails.
            pass

        by_name = cast(dict[str, Any], group_by_id_getter(site_id=site_id, name=wlan_group))
        by_name_wlan_id = self._extract_wlan_id(by_name)
        if by_name_wlan_id is None:
            raise ValueError(f"Matched WLAN group '{wlan_group}' does not include a valid wlanId")
        return by_name_wlan_id

    def _default_list_params(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        final_params = {"page": 1, "pageSize": 1000}
        if params:
            final_params.update(params)
        return final_params

    def _resolve_by_name(self, *, site_id: str, wlan_id: str, name: str) -> dict[str, Any]:
        response = self.client.get(
            self._path(f"/openapi/v1/sites/{site_id}/wireless-network/wlans/{wlan_id}/ssids"),
            params=self._default_list_params({"searchKey": name}),
        )
        networks = self._coerce_list_response(cast(dict[str, Any], response))
        exact_matches = [item for item in networks if isinstance(item.get("name"), str) and item["name"] == name]
        if not exact_matches:
            raise ValueError(f"Wi-Fi network with name '{name}' was not found")
        if len(exact_matches) > 1:
            raise ValueError(f"Multiple Wi-Fi networks found with name '{name}'")
        return exact_matches[0]

    def all(
        self,
        *,
        site_id: str,
        wlan_group: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        wlan_id = self._resolve_wlan_group_id(site_id=site_id, wlan_group=wlan_group)
        response = self.client.get(
            self._path(f"/openapi/v1/sites/{site_id}/wireless-network/wlans/{wlan_id}/ssids"),
            params=self._default_list_params(params),
        )
        return self._coerce_list_response(cast(dict[str, Any], response))

    def get(
        self,
        *,
        site_id: str,
        wlan_group: str,
        id: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        if (id is None) == (name is None):
            raise ValueError("Provide exactly one of 'id' or 'name'")

        wlan_id = self._resolve_wlan_group_id(site_id=site_id, wlan_group=wlan_group)
        if id is not None:
            response = self.client.get(
                self._path(f"/openapi/v1/sites/{site_id}/wireless-network/wlans/{wlan_id}/ssids/{id}")
            )
            payload = cast(dict[str, Any], response)
            result = payload.get("result")
            if isinstance(result, dict):
                return result
            return payload

        matched = self._resolve_by_name(site_id=site_id, wlan_id=wlan_id, name=cast(str, name))
        ssid_id = self._extract_ssid_id(matched)
        if ssid_id is None:
            raise ValueError(f"Matched Wi-Fi network '{name}' does not include a valid ssidId")
        return self.get(site_id=site_id, wlan_group=wlan_group, id=ssid_id)

    def delete(
        self,
        *,
        site_id: str,
        wlan_group: str,
        id: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        if (id is None) == (name is None):
            raise ValueError("Provide exactly one of 'id' or 'name'")

        wlan_id = self._resolve_wlan_group_id(site_id=site_id, wlan_group=wlan_group)
        ssid_id = id
        if ssid_id is None:
            matched = self._resolve_by_name(site_id=site_id, wlan_id=wlan_id, name=cast(str, name))
            ssid_id = self._extract_ssid_id(matched)
            if ssid_id is None:
                raise ValueError(f"Matched Wi-Fi network '{name}' does not include a valid ssidId")

        response = self.client.delete(
            self._path(f"/openapi/v1/sites/{site_id}/wireless-network/wlans/{wlan_id}/ssids/{ssid_id}")
        )
        return cast(dict[str, Any], response)

    def create(
        self,
        *,
        site_id: str,
        wlan_group: str,
        type: str,
        ssid: str,
        network_data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        network_type = self._normalize_network_type(type)
        self._validate_type(network_type)
        self._validate_ssid_inputs(ssid=ssid, network_data=network_data, kwargs=kwargs)

        wlan_id = self._resolve_wlan_group_id(site_id=site_id, wlan_group=wlan_group)
        payload = self._build_default_create_payload(ssid=ssid, network_type=network_type)
        self._apply_type_specific_settings(payload=payload, network_type=network_type, kwargs=kwargs)
        self._apply_vlan_setting(payload=payload, kwargs=kwargs)

        if network_data:
            payload.update(network_data)
        payload.update(kwargs)
        payload["name"] = ssid
        payload.pop("vlan", None)

        self._validate_required_payload_fields(payload)
        self._validate_security_type_requirements(network_type=network_type, payload=payload)

        response = self.client.post(
            self._path(f"/openapi/v1/sites/{site_id}/wireless-network/wlans/{wlan_id}/ssids"),
            json=payload,
        )
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
