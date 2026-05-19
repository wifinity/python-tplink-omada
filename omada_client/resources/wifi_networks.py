"""WiFi network operations for Omada."""

from __future__ import annotations

from typing import Any, Dict, cast

from omada_client.exceptions import WiFiNetworkPartiallyConfiguredError
from omada_client.wifi_payload_utils import (
    _build_dpsk_radius_setting,
    _build_ppsk_local_setting,
    _build_rate_limit_profile_body,
    _build_vlan_pool_setting,
    _default_ppsk_psk_setting,
    ssid_detail_to_basic_config_patch,
)

_SUPPORTED_WIFI_TYPES = ("open", "open-isolated", "aaa", "psk", "dpsk", "ppsk_local")

# Public type aliases normalized before validation (canonical keys in _TYPE_TO_SECURITY).
_NETWORK_TYPE_ALIASES: dict[str, str] = {
    "ppsk-local": "ppsk_local",
}

# Top-level list item keys accepted by ``filter`` (strict); ``ssid`` matches JSON ``name``.
_FILTER_CRITERIA_KEYS: frozenset[str] = frozenset(
    {
        "autoWanAccess",
        "band",
        "broadcast",
        "enable11r",
        "entSetting",
        "greEnable",
        "guestNetEnable",
        "hidePwd",
        "mloEnable",
        "name",
        "oweEnable",
        "pmfMode",
        "ppskSetting",
        "prohibitWifiShare",
        "pskSetting",
        "security",
        "ssid",
        "ssidId",
        "vlanEnable",
        "vlanId",
        "vlanSetting",
    }
)
_TYPE_TO_SECURITY = {
    "open": 0,
    "open-isolated": 0,
    "aaa": 2,
    "psk": 3,
    "ppsk_local": 4,
    "dpsk": 5,
}

# Default PMF mode per security type (Omada: 1 mandatory, 2 capable, 3 disable).
_DEFAULT_PMF_MODE_BY_TYPE: dict[str, int] = {
    "open": 2,
    "open-isolated": 2,
    "aaa": 2,
    "psk": 3,
    "ppsk_local": 3,
    "dpsk": 3,
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

    def _extract_ssid_id_from_response(self, response: dict[str, Any]) -> str | None:
        result = response.get("result")
        if isinstance(result, dict):
            ssid_id = self._extract_ssid_id(result)
            if ssid_id is not None:
                return ssid_id
        return self._extract_ssid_id(response)

    def _resolve_ssid_id_after_create(
        self,
        *,
        site_id: str,
        wlan_id: str,
        broadcast: str,
        create_response: dict[str, Any],
    ) -> str:
        ssid_id = self._extract_ssid_id_from_response(create_response)
        if ssid_id is not None:
            return ssid_id
        matched = self._resolve_by_name(site_id=site_id, wlan_id=wlan_id, name=broadcast)
        ssid_id = self._extract_ssid_id(matched)
        if ssid_id is None:
            raise ValueError(
                "Could not resolve ssidId after create; post-create PATCH requires ssidId in the create response or list lookup"
            )
        return ssid_id

    @staticmethod
    def _validate_rate_control_dict(rate_control: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(rate_control, dict):
            raise ValueError("rate_control must be a dict when provided")
        if not rate_control:
            raise ValueError("rate_control must be a non-empty dict")
        if "rateControl" in rate_control:
            raise ValueError(
                "PATCH body must be flat UpdateSsidRateControlOpenApiVO fields; "
                "do not wrap settings under 'rateControl' (GET detail nests under detail['rateControl'])"
            )
        return dict(rate_control)

    @staticmethod
    def _validate_multicast_config_dict(multicast_config: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(multicast_config, dict):
            raise ValueError("multicast_config must be a dict when provided")
        if not multicast_config:
            raise ValueError("multicast_config must be a non-empty dict")
        if "multiCast" in multicast_config:
            raise ValueError(
                "PATCH body must be flat UpdateSsidMultiCastOpenApiVO fields; "
                "do not wrap settings under 'multiCast' (GET detail nests under detail['multiCast'])"
            )
        return dict(multicast_config)

    def _list_rate_limit_profiles(self, *, site_id: str) -> list[dict[str, Any]]:
        response = self.client.get(
            self._path(f"/openapi/v1/sites/{site_id}/rate-limit-profiles"),
        )
        return self._coerce_list_response(cast(Dict[str, Any], response))

    def _lookup_rate_limit_profile_id_by_name(self, *, site_id: str, name: str) -> str:
        if not isinstance(name, str) or not name:
            raise ValueError("rate_limit_profile_name must be a non-empty string")
        profiles = self._list_rate_limit_profiles(site_id=site_id)
        matches = [item for item in profiles if item.get("name") == name]
        if not matches:
            raise ValueError(
                f"No rate limit profile named '{name}' on site '{site_id}'. "
                "Create the profile in Omada or check the exact name spelling."
            )
        if len(matches) > 1:
            ids = [self._extract_profile_id(item) for item in matches]
            ids_display = ", ".join(i for i in ids if i)
            raise ValueError(
                f"Multiple rate limit profiles named '{name}' on site '{site_id}'"
                + (f" (profileIds: {ids_display})" if ids_display else "")
            )
        profile_id = self._extract_profile_id(matches[0])
        if profile_id is None:
            raise ValueError(f"Rate limit profile '{name}' does not include a valid profileId")
        return profile_id

    @staticmethod
    def _extract_profile_id(item: dict[str, Any]) -> str | None:
        value = item.get("profileId")
        if isinstance(value, str) and value:
            return value
        return None

    def _list_ppsk_profiles(self, *, site_id: str) -> list[dict[str, Any]]:
        response = self.client.get(
            self._path(f"/openapi/v1/sites/{site_id}/ppsk-profiles"),
        )
        return self._coerce_list_response(cast(Dict[str, Any], response))

    @staticmethod
    def _extract_ppsk_profile_id(item: dict[str, Any]) -> str | None:
        value = item.get("id")
        if isinstance(value, str) and value:
            return value
        return None

    def _lookup_ppsk_profile_id_by_name(self, *, site_id: str, profile_name: str) -> str:
        if not isinstance(profile_name, str) or not profile_name:
            raise ValueError("ppsk_profile_name must be a non-empty string")
        profiles = self._list_ppsk_profiles(site_id=site_id)
        matches = [item for item in profiles if item.get("profileName") == profile_name]
        if not matches:
            raise ValueError(
                f"No PPSK profile named '{profile_name}' on site '{site_id}'. "
                "Create the profile in Omada or check the exact profileName spelling."
            )
        if len(matches) > 1:
            ids = [self._extract_ppsk_profile_id(item) for item in matches]
            ids_display = ", ".join(i for i in ids if i)
            raise ValueError(
                f"Multiple PPSK profiles named '{profile_name}' on site '{site_id}'"
                + (f" (ids: {ids_display})" if ids_display else "")
            )
        profile_id = self._extract_ppsk_profile_id(matches[0])
        if profile_id is None:
            raise ValueError(f"PPSK profile '{profile_name}' does not include a valid id")
        return profile_id

    def _list_radius_profiles(self, *, site_id: str) -> list[dict[str, Any]]:
        response = self.client.get(
            self._path(f"/openapi/v1/sites/{site_id}/profiles/radius"),
        )
        return self._coerce_list_response(cast(Dict[str, Any], response))

    @staticmethod
    def _extract_radius_profile_id(item: dict[str, Any]) -> str | None:
        value = item.get("radiusProfileId")
        if isinstance(value, str) and value:
            return value
        return None

    def _lookup_radius_profile_id_by_name(self, *, site_id: str, profile_name: str) -> str:
        if not isinstance(profile_name, str) or not profile_name:
            raise ValueError("radius_profile_name must be a non-empty string")
        profiles = self._list_radius_profiles(site_id=site_id)
        matches = [item for item in profiles if item.get("name") == profile_name]
        if not matches:
            raise ValueError(
                f"No RADIUS profile named '{profile_name}' on site '{site_id}'. "
                "Create the profile in Omada or check the exact name spelling."
            )
        if len(matches) > 1:
            ids = [self._extract_radius_profile_id(item) for item in matches]
            ids_display = ", ".join(i for i in ids if i)
            raise ValueError(
                f"Multiple RADIUS profiles named '{profile_name}' on site '{site_id}'"
                + (f" (radiusProfileIds: {ids_display})" if ids_display else "")
            )
        profile_id = self._extract_radius_profile_id(matches[0])
        if profile_id is None:
            raise ValueError(f"RADIUS profile '{profile_name}' does not include a valid radiusProfileId")
        return profile_id

    @staticmethod
    def _validate_type(network_type: str) -> None:
        if network_type == "hotspot20":
            raise ValueError(
                "Wi-Fi type 'hotspot20' is not supported by this SDK (Omada Hotspot 2.0 / portal "
                "payloads are not implemented). Use raw client requests if required."
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
        return _NETWORK_TYPE_ALIASES.get(network_type, network_type)

    @staticmethod
    def _resolve_broadcast_name(*, ssid: str | None, name: str | None) -> str:
        if ssid is not None and name is not None:
            if ssid != name:
                raise ValueError("When both 'ssid' and 'name' are provided, they must be identical")
            return ssid
        if ssid is not None:
            if not isinstance(ssid, str) or not ssid:
                raise ValueError("ssid must be a non-empty string when provided")
            return ssid
        if name is not None:
            if not isinstance(name, str) or not name:
                raise ValueError("name must be a non-empty string when provided")
            return name
        raise ValueError("Provide 'ssid' and/or 'name' as the SSID broadcast name (at least one required)")

    @staticmethod
    def _validate_network_data_for_create(*, network_data: dict[str, Any] | None) -> None:
        if network_data is not None and "name" in network_data:
            raise ValueError("network_data must not include 'name'; set ssid and/or name parameters")

    @staticmethod
    def _default_pmf_mode(network_type: str) -> int:
        return _DEFAULT_PMF_MODE_BY_TYPE[network_type]

    @staticmethod
    def _build_default_create_payload(
        *, broadcast_name: str, network_type: str, pmf_mode: int | None = None
    ) -> dict[str, Any]:
        guest_default = network_type == "open-isolated"
        pmf = pmf_mode if pmf_mode is not None else WiFiNetworksResource._default_pmf_mode(network_type)
        if not isinstance(pmf, int):
            raise ValueError("pmf_mode must be an integer when provided")
        return {
            "band": 3,
            "broadcast": True,
            "deviceType": 1,
            "enable11r": False,
            "guestNetEnable": guest_default,
            "hidePwd": False,
            "mloEnable": False,
            "name": broadcast_name,
            "pmfMode": pmf,
            "security": _TYPE_TO_SECURITY[network_type],
            "vlanEnable": False,
        }

    @staticmethod
    def _apply_open_guest_flag(*, payload: dict[str, Any], network_type: str, guest_network: bool | None) -> None:
        if network_type != "open" or guest_network is None:
            return
        payload["guestNetEnable"] = bool(guest_network)

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

    @staticmethod
    def _validate_type_param_compatibility(*, network_type: str, kwargs: dict[str, Any]) -> None:
        """Reject auth kwargs that do not match the requested Wi-Fi type."""
        if "psk" in kwargs and network_type != "psk":
            raise ValueError(
                f"psk is only valid for type='psk' (WPA-Personal); got type={network_type!r}. "
                "Corporate PPSK uses type='ppsk_local' with ppsk_profile_name=."
            )
        if "psk_setting" in kwargs and network_type not in ("psk", "ppsk_local"):
            raise ValueError(
                f"psk_setting is only valid for type='psk' or type='ppsk_local'; got type={network_type!r}"
            )
        if "ppsk_setting" in kwargs and network_type not in ("ppsk_local", "dpsk"):
            raise ValueError(
                f"ppsk_setting is only valid for type='ppsk_local' or type='dpsk'; got type={network_type!r}. "
                "WPA-Personal uses type='psk' with psk=."
            )

    @staticmethod
    def _validate_profile_id_params(
        *,
        network_type: str,
        ppsk_profile_name: str | None,
        radius_profile_name: str | None,
        nas_id: str | None,
    ) -> None:
        if ppsk_profile_name is not None and network_type != "ppsk_local":
            raise ValueError(
                "ppsk_profile_name is only valid for type='ppsk_local' "
                "(WPA-Personal / shared passphrase uses type='psk' with psk=)"
            )
        if radius_profile_name is not None and network_type != "dpsk":
            raise ValueError("radius_profile_name is only valid for type='dpsk'")
        if radius_profile_name is not None and nas_id is None:
            raise ValueError("type='dpsk' with radius_profile_name requires nas_id")
        if nas_id is not None and radius_profile_name is None:
            raise ValueError("nas_id requires radius_profile_name for type='dpsk'")

    @staticmethod
    def _apply_ppsk_profile_id_shortcut(
        *,
        payload: dict[str, Any],
        ppsk_profile_id: str,
        mac_format: int,
        kwargs: dict[str, Any],
    ) -> None:
        if kwargs.get("ppsk_setting") is not None:
            raise ValueError("Provide ppsk_profile_name or ppsk_setting, not both")
        payload["ppskSetting"] = _build_ppsk_local_setting(
            ppsk_profile_id=ppsk_profile_id,
            mac_format=mac_format,
        )
        if payload.get("pskSetting") is None and kwargs.get("psk") is None:
            payload["pskSetting"] = _default_ppsk_psk_setting()

    @staticmethod
    def _apply_radius_profile_id_shortcut(
        *,
        payload: dict[str, Any],
        radius_profile_id: str,
        nas_id: str | None,
        mac_format: int,
        kwargs: dict[str, Any],
    ) -> None:
        if kwargs.get("ppsk_setting") is not None:
            raise ValueError("Provide radius_profile_name or ppsk_setting, not both")
        if nas_id is None:
            raise ValueError("type='dpsk' with radius_profile_name requires nas_id")
        payload["ppskSetting"] = _build_dpsk_radius_setting(
            radius_profile_id=radius_profile_id,
            nas_id=nas_id,
            mac_format=mac_format,
        )
        if payload.get("pskSetting") is None and kwargs.get("psk") is None:
            payload["pskSetting"] = _default_ppsk_psk_setting()

    def _apply_profile_id_shortcuts(
        self,
        *,
        site_id: str,
        payload: dict[str, Any],
        network_type: str,
        ppsk_profile_name: str | None,
        radius_profile_name: str | None,
        nas_id: str | None,
        mac_format: int,
        kwargs: dict[str, Any],
    ) -> None:
        self._validate_profile_id_params(
            network_type=network_type,
            ppsk_profile_name=ppsk_profile_name,
            radius_profile_name=radius_profile_name,
            nas_id=nas_id,
        )
        if ppsk_profile_name is not None:
            if kwargs.get("ppsk_setting") is not None:
                raise ValueError("Provide ppsk_profile_name or ppsk_setting, not both")
            ppsk_profile_id = self._lookup_ppsk_profile_id_by_name(
                site_id=site_id,
                profile_name=ppsk_profile_name,
            )
            self._apply_ppsk_profile_id_shortcut(
                payload=payload,
                ppsk_profile_id=ppsk_profile_id,
                mac_format=mac_format,
                kwargs=kwargs,
            )
        if radius_profile_name is not None:
            if kwargs.get("ppsk_setting") is not None:
                raise ValueError("Provide radius_profile_name or ppsk_setting, not both")
            radius_profile_id = self._lookup_radius_profile_id_by_name(
                site_id=site_id,
                profile_name=radius_profile_name,
            )
            self._apply_radius_profile_id_shortcut(
                payload=payload,
                radius_profile_id=radius_profile_id,
                nas_id=nas_id,
                mac_format=mac_format,
                kwargs=kwargs,
            )

    def _apply_type_specific_settings(
        self, *, payload: dict[str, Any], network_type: str, kwargs: dict[str, Any]
    ) -> None:
        if network_type == "psk":
            self._apply_psk_settings(payload=payload, kwargs=kwargs)
        if network_type == "dpsk":
            self._apply_dpsk_settings(payload=payload, kwargs=kwargs)
        if network_type == "ppsk_local":
            self._apply_psk_settings(payload=payload, kwargs=kwargs)
            self._apply_dpsk_settings(payload=payload, kwargs=kwargs)
        if network_type == "aaa":
            self._apply_aaa_settings(payload=payload, kwargs=kwargs)

    @staticmethod
    def _vlan_id_from_pool_setting(vlan_setting: dict[str, Any]) -> int | None:
        """Infer ``vlanId`` from a single-ID vlan pool ``vlanSetting`` when possible."""
        custom = vlan_setting.get("customConfig")
        if not isinstance(custom, dict):
            return None
        pool_ids = custom.get("vlanPoolIds")
        if not isinstance(pool_ids, str) or not pool_ids.isdigit():
            return None
        vlan = int(pool_ids)
        if 1 <= vlan <= 4094:
            return vlan
        return None

    @staticmethod
    def _apply_vlan_setting(*, payload: dict[str, Any], vlan: int | None) -> None:
        if vlan is None:
            return
        if not isinstance(vlan, int) or not (1 <= vlan <= 4094):
            raise ValueError("vlan must be an integer in range 1..4094")
        payload["vlanEnable"] = True
        payload["vlanId"] = vlan
        payload["vlanSetting"] = _build_vlan_pool_setting(vlan)

    @staticmethod
    def _apply_vlan_setting_object(*, payload: dict[str, Any], vlan_setting: dict[str, Any]) -> None:
        payload["vlanEnable"] = True
        vs = dict(vlan_setting)
        payload["vlanSetting"] = vs
        vlan_id = WiFiNetworksResource._vlan_id_from_pool_setting(vs)
        if vlan_id is not None:
            payload["vlanId"] = vlan_id

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
            raise ValueError("type='dpsk' requires ppsk_setting (dict) or radius_profile_name with nas_id")
        if network_type == "ppsk_local":
            if not isinstance(payload.get("pskSetting"), dict):
                raise ValueError("type='ppsk_local' requires psk_setting (dict), psk (string), or ppsk_profile_name")
            if not isinstance(payload.get("ppskSetting"), dict):
                raise ValueError("type='ppsk_local' requires ppsk_setting (dict) or ppsk_profile_name")
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
            by_id = cast(Dict[str, Any], group_by_id_getter(site_id=site_id, id=wlan_group))
            by_id_wlan_id = self._extract_wlan_id(by_id)
            if by_id_wlan_id is not None:
                return by_id_wlan_id
            # Some controllers return minimal/empty detail payloads; if id lookup itself
            # succeeded, treat the caller input as the resolved wlan id.
            return wlan_group
        except Exception:
            # Fall back to name-based resolution when id lookup fails.
            pass

        by_name = cast(Dict[str, Any], group_by_id_getter(site_id=site_id, name=wlan_group))
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
        networks = self._coerce_list_response(cast(Dict[str, Any], response))
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
        return self._coerce_list_response(cast(Dict[str, Any], response))

    @staticmethod
    def _list_search_params_for_filter(criteria: dict[str, Any]) -> dict[str, Any] | None:
        """When criteria are only broadcast-name selectors, narrow the list GET with ``searchKey``."""
        keys = frozenset(criteria.keys())
        if keys - {"ssid", "name"}:
            return None
        if "ssid" in criteria and "name" in criteria and criteria["ssid"] != criteria["name"]:
            raise ValueError("filter criteria 'ssid' and 'name' must match when both are provided")
        term = criteria.get("name")
        if term is None:
            term = criteria.get("ssid")
        if isinstance(term, str) and term:
            return {"searchKey": term}
        return None

    @staticmethod
    def _item_matches_filter_criteria(item: dict[str, Any], criteria: dict[str, Any]) -> bool:
        for key, expected in criteria.items():
            actual = item.get("name") if key == "ssid" else item.get(key)
            if actual != expected:
                return False
        return True

    def filter(
        self,
        *,
        site_id: str,
        wlan_group: str,
        **criteria: Any,
    ) -> list[dict[str, Any]]:
        if not criteria:
            raise ValueError("Provide at least one filter criterion as a keyword argument")
        unknown = frozenset(criteria) - _FILTER_CRITERIA_KEYS
        if unknown:
            raise ValueError(f"Unsupported filter criteria: {', '.join(sorted(unknown))}")

        list_params = self._list_search_params_for_filter(dict(criteria))
        items = self.all(site_id=site_id, wlan_group=wlan_group, params=list_params)
        return [item for item in items if self._item_matches_filter_criteria(item, criteria)]

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
            payload = cast(Dict[str, Any], response)
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
        return cast(Dict[str, Any], response)

    def update_basic_config(
        self,
        *,
        site_id: str,
        wlan_group: str,
        id: str | None = None,
        name: str | None = None,
        network_data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if (id is None) == (name is None):
            raise ValueError("Provide exactly one of 'id' or 'name'")

        detail = self.get(site_id=site_id, wlan_group=wlan_group, id=id, name=name)
        overrides: dict[str, Any] = {}
        if network_data is not None:
            if not isinstance(network_data, dict):
                raise ValueError("network_data must be a dict when provided")
            overrides.update(network_data)
        overrides.update(kwargs)
        payload = ssid_detail_to_basic_config_patch(detail, overrides if overrides else None)

        ssid_id = self._extract_ssid_id(detail)
        if ssid_id is None:
            raise ValueError("SSID detail did not include a valid ssidId for update")

        wlan_id = self._resolve_wlan_group_id(site_id=site_id, wlan_group=wlan_group)
        path = f"/openapi/v1/sites/{site_id}/wireless-network/wlans/{wlan_id}/ssids/{ssid_id}/update-basic-config"
        response = self.client.patch(self._path(path), json=payload)
        return cast(Dict[str, Any], response)

    def update_multicast_config(
        self,
        *,
        site_id: str,
        wlan_group: str,
        id: str | None = None,
        name: str | None = None,
        multicast_config: dict[str, Any],
    ) -> dict[str, Any]:
        if (id is None) == (name is None):
            raise ValueError("Provide exactly one of 'id' or 'name'")

        payload = self._validate_multicast_config_dict(multicast_config)

        wlan_id = self._resolve_wlan_group_id(site_id=site_id, wlan_group=wlan_group)
        ssid_id = id
        if ssid_id is None:
            matched = self._resolve_by_name(site_id=site_id, wlan_id=wlan_id, name=cast(str, name))
            ssid_id = self._extract_ssid_id(matched)
            if ssid_id is None:
                raise ValueError(f"Matched Wi-Fi network '{name}' does not include a valid ssidId")

        path = (
            f"/openapi/v1/sites/{site_id}/wireless-network/wlans/{wlan_id}/ssids/{ssid_id}" "/update-multicast-config"
        )
        response = self.client.patch(self._path(path), json=payload)
        return cast(Dict[str, Any], response)

    def update_rate_control(
        self,
        *,
        site_id: str,
        wlan_group: str,
        id: str | None = None,
        name: str | None = None,
        rate_control: dict[str, Any],
    ) -> dict[str, Any]:
        if (id is None) == (name is None):
            raise ValueError("Provide exactly one of 'id' or 'name'")

        payload = self._validate_rate_control_dict(rate_control)

        wlan_id = self._resolve_wlan_group_id(site_id=site_id, wlan_group=wlan_group)
        ssid_id = id
        if ssid_id is None:
            matched = self._resolve_by_name(site_id=site_id, wlan_id=wlan_id, name=cast(str, name))
            ssid_id = self._extract_ssid_id(matched)
            if ssid_id is None:
                raise ValueError(f"Matched Wi-Fi network '{name}' does not include a valid ssidId")

        path = f"/openapi/v1/sites/{site_id}/wireless-network/wlans/{wlan_id}/ssids/{ssid_id}" "/update-rate-control"
        response = self.client.patch(self._path(path), json=payload)
        return cast(Dict[str, Any], response)

    def update_rate_limit(
        self,
        *,
        site_id: str,
        wlan_group: str,
        id: str | None = None,
        name: str | None = None,
        rate_limit_profile_name: str,
    ) -> dict[str, Any]:
        if (id is None) == (name is None):
            raise ValueError("Provide exactly one of 'id' or 'name'")

        profile_id = self._lookup_rate_limit_profile_id_by_name(
            site_id=site_id,
            name=rate_limit_profile_name,
        )
        payload = _build_rate_limit_profile_body(profile_id)

        wlan_id = self._resolve_wlan_group_id(site_id=site_id, wlan_group=wlan_group)
        ssid_id = id
        if ssid_id is None:
            matched = self._resolve_by_name(site_id=site_id, wlan_id=wlan_id, name=cast(str, name))
            ssid_id = self._extract_ssid_id(matched)
            if ssid_id is None:
                raise ValueError(f"Matched Wi-Fi network '{name}' does not include a valid ssidId")

        path = f"/openapi/v1/sites/{site_id}/wireless-network/wlans/{wlan_id}/ssids/{ssid_id}" "/update-rate-limit"
        response = self.client.patch(self._path(path), json=payload)
        return cast(Dict[str, Any], response)

    def _validate_post_create_inputs(
        self,
        *,
        multicast_config: dict[str, Any] | None,
        rate_control: dict[str, Any] | None,
        rate_limit_profile_name: str | None,
    ) -> None:
        """Validate post-create PATCH inputs before the POST.

        A malformed input is a usage error and must raise without creating an SSID, rather than
        surfacing as a ``WiFiNetworkPartiallyConfiguredError`` after a successful POST.
        """
        if multicast_config is not None:
            self._validate_multicast_config_dict(multicast_config)
        if rate_control is not None:
            self._validate_rate_control_dict(rate_control)
        if rate_limit_profile_name is not None and (
            not isinstance(rate_limit_profile_name, str) or not rate_limit_profile_name
        ):
            raise ValueError("rate_limit_profile_name must be a non-empty string")

    def _apply_post_create_patches(
        self,
        *,
        site_id: str,
        wlan_group: str,
        wlan_id: str,
        broadcast: str,
        create_response: dict[str, Any],
        multicast_config: dict[str, Any] | None,
        rate_control: dict[str, Any] | None,
        rate_limit_profile_name: str | None,
    ) -> None:
        """Run the opt-in post-create PATCHes; wrap any failure with the created ``ssidId``."""
        if multicast_config is None and rate_control is None and rate_limit_profile_name is None:
            return
        ssid_id = self._resolve_ssid_id_after_create(
            site_id=site_id,
            wlan_id=wlan_id,
            broadcast=broadcast,
            create_response=create_response,
        )
        completed_steps: list[str] = []
        step = ""
        try:
            if multicast_config is not None:
                step = "update-multicast-config"
                self.update_multicast_config(
                    site_id=site_id, wlan_group=wlan_group, id=ssid_id, multicast_config=multicast_config
                )
                completed_steps.append(step)
            if rate_control is not None:
                step = "update-rate-control"
                self.update_rate_control(site_id=site_id, wlan_group=wlan_group, id=ssid_id, rate_control=rate_control)
                completed_steps.append(step)
            if rate_limit_profile_name is not None:
                step = "update-rate-limit"
                self.update_rate_limit(
                    site_id=site_id,
                    wlan_group=wlan_group,
                    id=ssid_id,
                    rate_limit_profile_name=rate_limit_profile_name,
                )
                completed_steps.append(step)
        except Exception as exc:
            raise WiFiNetworkPartiallyConfiguredError(
                ssid_id=ssid_id,
                failed_step=step,
                completed_steps=completed_steps,
            ) from exc

    def create(
        self,
        *,
        site_id: str,
        wlan_group: str,
        type: str,
        ssid: str | None = None,
        name: str | None = None,
        network_data: dict[str, Any] | None = None,
        vlan: int | None = None,
        vlan_setting: dict[str, Any] | None = None,
        guest_network: bool | None = None,
        pmf_mode: int | None = None,
        ppsk_profile_name: str | None = None,
        radius_profile_name: str | None = None,
        nas_id: str | None = None,
        mac_format: int = 2,
        multicast_config: dict[str, Any] | None = None,
        rate_control: dict[str, Any] | None = None,
        rate_limit_profile_name: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        network_type = self._normalize_network_type(type)
        self._validate_type(network_type)
        broadcast = self._resolve_broadcast_name(ssid=ssid, name=name)
        self._validate_network_data_for_create(network_data=network_data)
        self._validate_post_create_inputs(
            multicast_config=multicast_config,
            rate_control=rate_control,
            rate_limit_profile_name=rate_limit_profile_name,
        )

        kw = dict(kwargs)
        self._validate_type_param_compatibility(network_type=network_type, kwargs=kw)
        self._validate_profile_id_params(
            network_type=network_type,
            ppsk_profile_name=ppsk_profile_name,
            radius_profile_name=radius_profile_name,
            nas_id=nas_id,
        )

        wlan_id = self._resolve_wlan_group_id(site_id=site_id, wlan_group=wlan_group)
        payload = self._build_default_create_payload(
            broadcast_name=broadcast,
            network_type=network_type,
            pmf_mode=pmf_mode,
        )
        self._apply_open_guest_flag(payload=payload, network_type=network_type, guest_network=guest_network)

        if vlan_setting is not None:
            if not isinstance(vlan_setting, dict):
                raise ValueError("vlan_setting must be a dict when provided")
            if vlan is not None:
                raise ValueError("Provide vlan integer shortcut or vlan_setting, not both")
            self._apply_vlan_setting_object(payload=payload, vlan_setting=vlan_setting)
        else:
            self._apply_vlan_setting(payload=payload, vlan=vlan)

        self._apply_profile_id_shortcuts(
            site_id=site_id,
            payload=payload,
            network_type=network_type,
            ppsk_profile_name=ppsk_profile_name,
            radius_profile_name=radius_profile_name,
            nas_id=nas_id,
            mac_format=mac_format,
            kwargs=kw,
        )
        self._apply_type_specific_settings(payload=payload, network_type=network_type, kwargs=kw)

        if network_data:
            payload.update(network_data)
        payload.update(kw)
        payload["name"] = broadcast
        payload.pop("vlan", None)

        self._validate_required_payload_fields(payload)
        self._validate_security_type_requirements(network_type=network_type, payload=payload)

        response = self.client.post(
            self._path(f"/openapi/v1/sites/{site_id}/wireless-network/wlans/{wlan_id}/ssids"),
            json=payload,
        )
        self._apply_post_create_patches(
            site_id=site_id,
            wlan_group=wlan_group,
            wlan_id=wlan_id,
            broadcast=broadcast,
            create_response=cast(Dict[str, Any], response),
            multicast_config=multicast_config,
            rate_control=rate_control,
            rate_limit_profile_name=rate_limit_profile_name,
        )
        return cast(Dict[str, Any], response)

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
        return cast(Dict[str, Any], response)
