"""Tests for Wi-Fi payload builder helpers."""

from __future__ import annotations

import pytest

from omada_client.wifi_payload_utils import (
    _build_dpsk_radius_setting,
    _build_ppsk_local_setting,
    _build_rate_limit_profile_body,
    _build_vlan_pool_setting,
    ssid_detail_to_basic_config_patch,
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
