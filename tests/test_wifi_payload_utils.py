"""Tests for Wi-Fi payload builder helpers."""

from __future__ import annotations

import pytest

from omada_client.wifi_payload_utils import (
    _build_dpsk_radius_setting,
    _build_ppsk_local_setting,
    _build_rate_limit_profile_body,
    _build_vlan_pool_setting,
    ssid_detail_to_basic_config_patch,
    strip_ssid_detail_for_create,
)


def _detail_without_pmf(*, security: int) -> dict:
    """SSID detail as some controllers return it: no enable11r / pmfMode keys."""
    return {
        "name": "N",
        "band": 3,
        "broadcast": True,
        "security": security,
        "guestNetEnable": False,
        "mloEnable": False,
        "vlanEnable": False,
    }


def test_basic_config_patch_defaults_omitted_required_fields() -> None:
    out = ssid_detail_to_basic_config_patch(_detail_without_pmf(security=3))
    assert out["enable11r"] is False
    assert out["pmfMode"] == 3  # security 3 (psk) -> required


def test_basic_config_patch_pmf_default_follows_security() -> None:
    assert ssid_detail_to_basic_config_patch(_detail_without_pmf(security=0))["pmfMode"] == 2  # open -> capable
    assert ssid_detail_to_basic_config_patch(_detail_without_pmf(security=5))["pmfMode"] == 3  # dpsk -> required


def test_basic_config_patch_still_raises_on_missing_structural_field() -> None:
    detail = _detail_without_pmf(security=0)
    del detail["band"]
    with pytest.raises(ValueError, match="Missing required fields"):
        ssid_detail_to_basic_config_patch(detail)


def test_build_vlan_pool_setting() -> None:
    assert _build_vlan_pool_setting(98) == {
        "mode": 1,
        "customConfig": {"customMode": 1, "vlanPoolIds": "98"},
    }


def test_build_vlan_pool_setting_rejects_invalid_vlan() -> None:
    with pytest.raises(ValueError, match="vlan must be an integer"):
        _build_vlan_pool_setting(0)


def test_build_ppsk_local_setting() -> None:
    assert _build_ppsk_local_setting(ppsk_profile_id="prof-1") == {
        "ppskProfileId": "prof-1",
        "macFormat": 2,
        "type": 0,
    }


def test_build_rate_limit_profile_body() -> None:
    body = _build_rate_limit_profile_body("prof-1")
    assert body["clientRateLimit"]["profileId"] == "prof-1"
    assert body["ssidRateLimit"]["profileId"] == "prof-1"
    assert body["clientRateLimit"]["customSetting"] == {
        "downLimitEnable": False,
        "upLimitEnable": False,
    }


def test_build_dpsk_radius_setting() -> None:
    assert _build_dpsk_radius_setting(
        radius_profile_id="rad-1",
        nas_id="SITE",
    ) == {
        "radiusProfileId": "rad-1",
        "macFormat": 2,
        "nasId": "SITE",
        "type": 2,
    }


def test_strip_ssid_detail_for_create_drops_ap_group_binding() -> None:
    detail = {"name": "Guest", "security": 0, "apGroupIds": ["g1"], "id": "s1", "ssidEnable": True}

    stripped = strip_ssid_detail_for_create(detail)

    assert stripped == {"name": "Guest", "security": 0, "ssidEnable": True}


def test_basic_config_patch_drops_custom_config_when_vlan_mode_is_zero() -> None:
    detail = {
        "name": "Guest",
        "band": 3,
        "broadcast": True,
        "guestNetEnable": False,
        "mloEnable": False,
        "security": 0,
        "vlanEnable": False,
        "vlanSetting": {"mode": 0, "customConfig": {}},
    }

    body = ssid_detail_to_basic_config_patch(detail)

    assert body["vlanSetting"] == {"mode": 0}


def test_basic_config_patch_keeps_custom_config_when_vlan_mode_is_set() -> None:
    vlan_setting = {"mode": 1, "customConfig": {"customMode": 1, "vlanPoolIds": "100"}}
    detail = {
        "name": "Guest",
        "band": 3,
        "broadcast": True,
        "guestNetEnable": False,
        "mloEnable": False,
        "security": 0,
        "vlanEnable": False,
        "vlanSetting": vlan_setting,
    }

    assert ssid_detail_to_basic_config_patch(detail)["vlanSetting"] == vlan_setting


def test_basic_config_patch_fills_none_pmf_mode_and_enable11r() -> None:
    detail = {
        "name": "Guest",
        "band": 3,
        "broadcast": True,
        "guestNetEnable": False,
        "mloEnable": False,
        "security": 3,
        "vlanEnable": False,
        "pmfMode": None,
        "enable11r": None,
    }

    body = ssid_detail_to_basic_config_patch(detail)

    assert body["pmfMode"] == 3
    assert body["enable11r"] is False
