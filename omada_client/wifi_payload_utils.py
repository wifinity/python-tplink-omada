"""Helpers for Omada Wi-Fi (SSID) API payloads."""

from __future__ import annotations

from typing import Any

# Keys allowed on CreateSsidOpenApiVO (Omada fixed OpenAPI); used to trim GET detail payloads.
_CREATE_SSID_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "band",
        "broadcast",
        "deviceType",
        "enable11r",
        "entSetting",
        "greEnable",
        "guestNetEnable",
        "hidePwd",
        "mloEnable",
        "name",
        "pmfMode",
        "ppskSetting",
        "prohibitWifiShare",
        "pskSetting",
        "security",
        "vlanEnable",
        "vlanId",
        "vlanSetting",
    }
)

# Keys on UpdateSsidBasicConfigOpenApiVO (Omada fixed OpenAPI).
_UPDATE_BASIC_CONFIG_ALLOWED_KEYS: frozenset[str] = frozenset(
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
        "vlanEnable",
        "vlanId",
        "vlanSetting",
    }
)


def _build_vlan_pool_setting(vlan: int) -> dict[str, Any]:
    """Build standard Omada ``vlanSetting`` for a single VLAN pool ID."""
    if not isinstance(vlan, int) or not (1 <= vlan <= 4094):
        raise ValueError("vlan must be an integer in range 1..4094")
    vlan_str = str(vlan)
    return {
        "mode": 1,
        "customConfig": {
            "customMode": 1,
            "vlanPoolIds": vlan_str,
        },
    }


def _build_ppsk_local_setting(*, ppsk_profile_id: str, mac_format: int = 2) -> dict[str, Any]:
    """Build ``ppskSetting`` for PPSK without RADIUS (``security=4`` / ``type='ppsk_local'``)."""
    if not isinstance(ppsk_profile_id, str) or not ppsk_profile_id:
        raise ValueError("ppsk_profile_id must be a non-empty string")
    if not isinstance(mac_format, int):
        raise ValueError("mac_format must be an integer")
    return {
        "ppskProfileId": ppsk_profile_id,
        "macFormat": mac_format,
        "type": 0,
    }


def _build_dpsk_radius_setting(
    *,
    radius_profile_id: str,
    nas_id: str,
    mac_format: int = 2,
) -> dict[str, Any]:
    """Build ``ppskSetting`` for PPSK with RADIUS (``security=5`` / ``type='dpsk'``)."""
    if not isinstance(radius_profile_id, str) or not radius_profile_id:
        raise ValueError("radius_profile_id must be a non-empty string")
    if not isinstance(nas_id, str) or not nas_id:
        raise ValueError("nas_id must be a non-empty string when radius_profile_id is set")
    if not isinstance(mac_format, int):
        raise ValueError("mac_format must be an integer")
    return {
        "radiusProfileId": radius_profile_id,
        "macFormat": mac_format,
        "nasId": nas_id,
        "type": 2,
    }


def _default_ppsk_psk_setting() -> dict[str, Any]:
    """PSK block for PPSK-family SSIDs (``ppsk_local`` / ``dpsk``) when no passphrase is supplied."""
    return {
        "versionPsk": 2,
        "encryptionPsk": 3,
        "gikRekeyPskEnable": False,
    }


def _build_rate_limit_profile_body(profile_id: str) -> dict[str, Any]:
    """Build ``UpdateSsidRateLimitOpenApiVO`` attaching a site rate-limit profile (limits off in customSetting).

    Matches ``docs/wlan_samples`` ``clientRateLimit`` / ``ssidRateLimit`` shape (GET nests under those keys;
    PATCH uses this flat pair at the top level).
    """
    if not isinstance(profile_id, str) or not profile_id:
        raise ValueError("profile_id must be a non-empty string")
    setting = {
        "profileId": profile_id,
        "customSetting": {"downLimitEnable": False, "upLimitEnable": False},
    }
    return {
        "clientRateLimit": dict(setting),
        "ssidRateLimit": dict(setting),
    }


_UPDATE_BASIC_CONFIG_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "band",
        "broadcast",
        "enable11r",
        "guestNetEnable",
        "mloEnable",
        "name",
        "pmfMode",
        "security",
        "vlanEnable",
    }
)


def _normalize_ssid_override_name(overrides: dict[str, Any]) -> None:
    if "ssid" not in overrides:
        return
    ssid_val = overrides.get("ssid")
    name_val = overrides.get("name")
    if name_val is not None and ssid_val is not None and name_val != ssid_val:
        raise ValueError("overrides must not set both 'ssid' and 'name' to different values")
    if name_val is None:
        overrides["name"] = overrides.pop("ssid")
    else:
        overrides.pop("ssid", None)


def strip_ssid_detail_for_create(detail: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of *detail* containing only keys valid for SSID create (POST body).

    Omada SSID **detail** responses include read-only and follow-up-only fields (for example
    ``ssidId``, rate limits, schedules). Create accepts the ``CreateSsidOpenApiVO`` subset; this
    helper drops everything else so callers can merge overrides then ``WiFiNetworksResource.create``.

    Unknown keys inside nested dicts are preserved as copied via ``dict()`` only at the top level;
    nested structures are not deep-sanitized.
    """
    return {k: detail[k] for k in detail if k in _CREATE_SSID_ALLOWED_KEYS}


def ssid_detail_to_basic_config_patch(
    detail: dict[str, Any], overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build a PATCH body for ``update-basic-config`` from GET SSID *detail* plus *overrides*.

    Projects *detail* onto ``UpdateSsidBasicConfigOpenApiVO`` keys, merges *overrides* (only allowed keys),
    and ensures the OpenAPI **required** basic-config fields are present. ``ssid`` in *overrides* is treated
    as an alias for JSON ``name`` (Omada broadcast SSID field).

    Raises:
        ValueError: If required fields are missing after merge, or if *overrides* contains unknown keys.
    """
    out: dict[str, Any] = {k: detail[k] for k in detail if k in _UPDATE_BASIC_CONFIG_ALLOWED_KEYS}
    if overrides:
        merged = dict(overrides)
        _normalize_ssid_override_name(merged)
        for key, value in merged.items():
            if key not in _UPDATE_BASIC_CONFIG_ALLOWED_KEYS:
                raise ValueError(f"Unknown override key for basic config: {key}")
            out[key] = value
    missing = sorted(k for k in _UPDATE_BASIC_CONFIG_REQUIRED_KEYS if k not in out)
    if missing:
        raise ValueError(
            "Missing required fields for SSID basic-config update after merge: "
            + ", ".join(missing)
            + ". Fetch detail first or supply them in overrides."
        )
    return out
