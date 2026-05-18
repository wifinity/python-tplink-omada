"""Tests for Wi-Fi payload builder helpers."""

from __future__ import annotations

import pytest

from omada_client.wifi_payload_utils import (
    _build_dpsk_radius_setting,
    _build_ppsk_local_setting,
    _build_rate_limit_profile_body,
    _build_vlan_pool_setting,
)


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
