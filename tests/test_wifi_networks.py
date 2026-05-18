from __future__ import annotations

from typing import Dict, cast

import pytest

from omada_client.exceptions import WiFiNetworkPartiallyConfiguredError
from omada_client.resources.wifi_networks import WiFiNetworksResource
from omada_client.wifi_payload_utils import ssid_detail_to_basic_config_patch, strip_ssid_detail_for_create


class DummyClient:
    def __init__(self) -> None:
        self.get_calls: list[tuple[str, object]] = []
        self.post_calls: list[tuple[str, object]] = []
        self.patch_calls: list[tuple[str, object]] = []
        self.delete_calls: list[tuple[str, object]] = []
        self.get_response = {"ok": True}
        self.get_responses: list[dict[str, object]] | None = None
        self.post_response = {"ok": True}
        self.patch_response = {"ok": True}
        self.delete_response = {"ok": True}
        self.wlan_groups = DummyWLANGroups()

    def get(self, path: str, params=None):
        self.get_calls.append((path, params))
        if isinstance(self.get_responses, list) and self.get_responses:
            return self.get_responses.pop(0)
        return self.get_response

    def post(self, path: str, json=None):
        self.post_calls.append((path, json))
        return self.post_response

    def patch(self, path: str, json=None):
        self.patch_calls.append((path, json))
        return self.patch_response

    def delete(self, path: str, json=None):
        self.delete_calls.append((path, json))
        return self.delete_response


class DummyWLANGroups:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.by_id: dict[str, dict[str, str]] = {}
        self.by_name: dict[str, dict[str, str]] = {}

    def get(self, *, site_id: str, id: str | None = None, name: str | None = None):
        if (id is None) == (name is None):
            raise ValueError("Provide exactly one of 'id' or 'name'")
        if id is not None:
            self.calls.append(("id", site_id, id))
            if id in self.by_id:
                return self.by_id[id]
            raise ValueError(f"id '{id}' not found")
        self.calls.append(("name", site_id, cast(str, name)))
        if name in self.by_name:
            return self.by_name[cast(str, name)]
        raise ValueError(f"name '{name}' not found")


def _wire_wlan_group(client: DummyClient, *, group_id: str, group_name: str) -> None:
    group = {"wlanId": group_id, "name": group_name}
    client.wlan_groups.by_id[group_id] = group
    client.wlan_groups.by_name[group_name] = group


def _rate_limit_profiles_response(*, profile_id: str = "p-default", name: str = "Default") -> dict[str, object]:
    return {"result": {"data": [{"name": name, "profileId": profile_id}]}}


def _ppsk_profiles_response(
    *,
    profile_name: str = "Services_PPSK_Profile",
    profile_id: str = "6a0229864bc9cf648f0c0ef0",
) -> dict[str, object]:
    return {"result": {"data": [{"profileName": profile_name, "id": profile_id}]}}


def _radius_profiles_response(
    *,
    profile_name: str = "Home Networking Wi-Fi",
    profile_id: str = "6a0244454bc9cf648f0c1090",
) -> dict[str, object]:
    return {"result": {"data": [{"name": profile_name, "radiusProfileId": profile_id}]}}


def _wire_dpsk_create(
    client: DummyClient,
    *,
    ssid_id: str | None = "s-new",
    profile_name: str = "Home Networking Wi-Fi",
    profile_id: str = "6a0244454bc9cf648f0c1090",
    rate_limit_profile_id: str = "p-default",
) -> None:
    """RADIUS profile list GET before POST; rate-limit profile list queued for optional post-create lookup."""
    if ssid_id is not None:
        client.post_response = {"result": {"ssidId": ssid_id}}
    else:
        client.post_response = {"ok": True}
    client.get_responses = [
        _radius_profiles_response(profile_name=profile_name, profile_id=profile_id),
        _rate_limit_profiles_response(profile_id=rate_limit_profile_id),
    ]


def _wire_ppsk_local_create(
    client: DummyClient,
    *,
    ssid_id: str | None = "s-new",
    profile_name: str = "Services_PPSK_Profile",
    profile_id: str = "6a0229864bc9cf648f0c0ef0",
    rate_limit_profile_id: str = "p-default",
) -> None:
    """PPSK profile list GET before POST; rate-limit profile list queued for optional post-create lookup."""
    if ssid_id is not None:
        client.post_response = {"result": {"ssidId": ssid_id}}
    else:
        client.post_response = {"ok": True}
    client.get_responses = [
        _ppsk_profiles_response(profile_name=profile_name, profile_id=profile_id),
        _rate_limit_profiles_response(profile_id=rate_limit_profile_id),
    ]


def _wire_post_create(
    client: DummyClient,
    *,
    ssid_id: str | None = "s-new",
    profile_id: str = "p-default",
) -> None:
    """POST ssidId; get_response holds the rate-limit profile list for an optional rate-limit lookup."""
    if ssid_id is not None:
        client.post_response = {"result": {"ssidId": ssid_id}}
    else:
        client.post_response = {"ok": True}
    client.get_response = _rate_limit_profiles_response(profile_id=profile_id)


def _expected_rate_limit_patch_body(profile_id: str = "p-default") -> dict[str, object]:
    return {
        "clientRateLimit": {
            "profileId": profile_id,
            "customSetting": {"downLimitEnable": False, "upLimitEnable": False},
        },
        "ssidRateLimit": {
            "profileId": profile_id,
            "customSetting": {"downLimitEnable": False, "upLimitEnable": False},
        },
    }


_GUEST_MULTICAST: dict[str, object] = {
    "multiCastEnable": True,
    "ipv6CastEnable": True,
    "channelUtil": 100,
    "arpCastEnable": True,
    "filterEnable": True,
    "filterMode": 15,
}

_SECURED_MULTICAST: dict[str, object] = {
    "multiCastEnable": True,
    "ipv6CastEnable": True,
    "channelUtil": 100,
    "arpCastEnable": True,
    "filterEnable": False,
}


def test_wifi_all_uses_group_id_directly() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.get_response = {"result": {"data": [{"ssidId": "s1", "name": "Guest"}]}}
    resource = WiFiNetworksResource(client)

    result = resource.all(site_id="s1", wlan_group="w1")

    assert result == [{"ssidId": "s1", "name": "Guest"}]
    assert client.wlan_groups.calls[0] == ("id", "s1", "w1")
    assert client.get_calls[0] == (
        "/openapi/v1/sites/s1/wireless-network/wlans/w1/ssids",
        {"page": 1, "pageSize": 1000},
    )


def test_wifi_all_resolves_group_name_when_id_lookup_fails() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.get_response = {"result": {"data": [{"ssidId": "s1", "name": "Guest"}]}}
    resource = WiFiNetworksResource(client)

    result = resource.all(site_id="s1", wlan_group="Corp")

    assert result == [{"ssidId": "s1", "name": "Guest"}]
    assert client.wlan_groups.calls[0] == ("id", "s1", "Corp")
    assert client.wlan_groups.calls[1] == ("name", "s1", "Corp")
    assert client.get_calls[0] == (
        "/openapi/v1/sites/s1/wireless-network/wlans/w1/ssids",
        {"page": 1, "pageSize": 1000},
    )


def test_wifi_get_by_name_fetches_detail_by_ssid_id() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.get_responses = [
        {"result": {"data": [{"ssidId": "s99", "name": "Guest"}]}},
        {"result": {"ssidId": "s99", "name": "Guest", "security": 0}},
    ]
    resource = WiFiNetworksResource(client)

    result = resource.get(site_id="s1", wlan_group="Corp", name="Guest")

    assert result == {"ssidId": "s99", "name": "Guest", "security": 0}
    assert client.get_calls[0] == (
        "/openapi/v1/sites/s1/wireless-network/wlans/w1/ssids",
        {"page": 1, "pageSize": 1000, "searchKey": "Guest"},
    )
    assert client.get_calls[1] == (
        "/openapi/v1/sites/s1/wireless-network/wlans/w1/ssids/s99",
        None,
    )


def test_wifi_get_by_name_uses_resolved_wlan_id_without_re_resolve() -> None:
    client = DummyClient()
    # Simulate controllers that do not return wlanId in detail-by-id response.
    client.wlan_groups.by_id["w1"] = {"name": "Corp"}
    client.get_responses = [
        {"result": {"data": [{"ssidId": "s99", "name": "Guest"}]}},
        {"result": {"ssidId": "s99", "name": "Guest", "security": 0}},
    ]
    resource = WiFiNetworksResource(client)

    result = resource.get(site_id="s1", wlan_group="w1", name="Guest")

    assert result == {"ssidId": "s99", "name": "Guest", "security": 0}
    assert client.wlan_groups.calls == [("id", "s1", "w1"), ("id", "s1", "w1")]
    assert client.get_calls[0] == (
        "/openapi/v1/sites/s1/wireless-network/wlans/w1/ssids",
        {"page": 1, "pageSize": 1000, "searchKey": "Guest"},
    )


def test_wifi_get_requires_exactly_one_selector() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="Provide exactly one of 'id' or 'name'"):
        resource.get(site_id="s1", wlan_group="w1")

    with pytest.raises(ValueError, match="Provide exactly one of 'id' or 'name'"):
        resource.get(site_id="s1", wlan_group="w1", id="x", name="Guest")


def test_wifi_delete_by_name_resolves_ssid_id() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.get_response = {"result": {"data": [{"ssidId": "s5", "name": "Guest"}]}}
    resource = WiFiNetworksResource(client)

    result = resource.delete(site_id="s1", wlan_group="w1", name="Guest")

    assert result == {"ok": True}
    assert client.delete_calls[0] == (
        "/openapi/v1/sites/s1/wireless-network/wlans/w1/ssids/s5",
        None,
    )


def test_wifi_create_psk_builds_payload_and_overrides() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client)
    resource = WiFiNetworksResource(client)

    resource.create(
        site_id="s1",
        wlan_group="Corp",
        type="psk",
        ssid="GuestSSID",
        psk="initial-pass",
        network_data={"band": 7},
        pmfMode=3,
    )

    assert client.post_calls[0][0] == "/openapi/v1/sites/s1/wireless-network/wlans/w1/ssids"
    sent = cast(Dict[str, object], client.post_calls[0][1])
    assert sent["security"] == 3
    assert sent["name"] == "GuestSSID"
    assert sent["band"] == 7
    assert sent["pmfMode"] == 3
    psk_setting = cast(Dict[str, object], sent["pskSetting"])
    assert psk_setting["securityKey"] == "initial-pass"
    assert psk_setting["versionPsk"] == 2
    assert psk_setting["encryptionPsk"] == 3
    assert psk_setting["gikRekeyPskEnable"] is False


def test_wifi_create_dpsk_maps_to_security_five() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client)
    resource = WiFiNetworksResource(client)

    resource.create(
        site_id="s1",
        wlan_group="w1",
        type="dpsk",
        ssid="GuestSSID",
        ppsk_setting={"radiusProfileId": "r1"},
    )

    sent = cast(Dict[str, object], client.post_calls[0][1])
    assert sent["security"] == 5
    assert "ppskSetting" in sent


def test_wifi_create_maps_vlan_shortcut_to_vlan_pool_setting() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client)
    resource = WiFiNetworksResource(client)

    resource.create(
        site_id="s1",
        wlan_group="w1",
        type="open",
        ssid="GuestSSID",
        vlan=99,
    )

    sent = cast(Dict[str, object], client.post_calls[0][1])
    assert sent["vlanEnable"] is True
    assert sent["vlanSetting"] == {
        "mode": 1,
        "customConfig": {"customMode": 1, "vlanPoolIds": "99"},
    }
    assert sent["vlanId"] == 99
    assert "vlan" not in sent


def test_wifi_create_vlan_setting_omits_vlan_id() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client)
    resource = WiFiNetworksResource(client)

    vs = {
        "mode": 1,
        "customConfig": {"customMode": 1, "vlanPoolIds": "98"},
    }
    resource.create(
        site_id="s1",
        wlan_group="w1",
        type="open",
        ssid="Guest",
        vlan_setting=vs,
    )

    sent = cast(Dict[str, object], client.post_calls[0][1])
    assert sent["vlanEnable"] is True
    assert sent["vlanSetting"] == vs
    assert sent["vlanId"] == 98


def test_wifi_create_rejects_vlan_and_vlan_setting_together() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="vlan integer shortcut or vlan_setting"):
        resource.create(
            site_id="s1",
            wlan_group="w1",
            type="open",
            ssid="Guest",
            vlan=10,
            vlan_setting={"mode": 1},
        )


def test_wifi_create_rejects_invalid_vlan_shortcut() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="vlan must be an integer in range 1..4094"):
        resource.create(
            site_id="s1",
            wlan_group="w1",
            type="open",
            ssid="GuestSSID",
            vlan=0,
        )


def test_wifi_create_open_isolated_type_sets_guest_net() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client)
    resource = WiFiNetworksResource(client)

    resource.create(site_id="s1", wlan_group="w1", type="open-isolated", ssid="G")

    sent = cast(Dict[str, object], client.post_calls[0][1])
    assert sent["security"] == 0
    assert sent["guestNetEnable"] is True


def test_wifi_create_rejects_guest_type() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="Invalid Wi-Fi type 'guest'"):
        resource.create(site_id="s1", wlan_group="w1", type="guest", ssid="G")


def test_wifi_create_open_with_guest_network_flag() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client)
    resource = WiFiNetworksResource(client)

    resource.create(site_id="s1", wlan_group="w1", type="open", ssid="O", guest_network=True)

    sent = cast(Dict[str, object], client.post_calls[0][1])
    assert sent["guestNetEnable"] is True


def test_wifi_create_ppsk_local_from_profile_name() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_ppsk_local_create(client)
    resource = WiFiNetworksResource(client)

    resource.create(
        site_id="s1",
        wlan_group="w1",
        type="ppsk_local",
        ssid="Corporate",
        vlan=999,
        ppsk_profile_name="Services_PPSK_Profile",
    )

    assert client.get_calls[0][0].endswith("/sites/s1/ppsk-profiles")
    sent = cast(Dict[str, object], client.post_calls[0][1])
    assert sent["security"] == 4
    assert sent["pmfMode"] == 3
    assert sent["vlanSetting"]["customConfig"]["vlanPoolIds"] == "999"
    ppsk = cast(Dict[str, object], sent["ppskSetting"])
    assert ppsk["ppskProfileId"] == "6a0229864bc9cf648f0c0ef0"
    assert ppsk["macFormat"] == 2
    assert ppsk["type"] == 0
    psk = cast(Dict[str, object], sent["pskSetting"])
    assert psk["versionPsk"] == 2
    assert psk["encryptionPsk"] == 3
    assert "securityKey" not in psk


def test_wifi_create_ppsk_local_fails_when_profile_name_missing() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.get_response = _ppsk_profiles_response(profile_name="Other-Profile")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="No PPSK profile named"):
        resource.create(
            site_id="s1",
            wlan_group="w1",
            type="ppsk_local",
            ssid="Corporate",
            ppsk_profile_name="Services_PPSK_Profile",
        )


def test_wifi_create_ppsk_local_fails_on_duplicate_profile_name() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.get_response = {
        "result": {
            "data": [
                {"profileName": "Services_PPSK_Profile", "id": "p1"},
                {"profileName": "Services_PPSK_Profile", "id": "p2"},
            ]
        }
    }
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="Multiple PPSK profiles named"):
        resource.create(
            site_id="s1",
            wlan_group="w1",
            type="ppsk_local",
            ssid="Corporate",
            ppsk_profile_name="Services_PPSK_Profile",
        )


def test_wifi_lookup_radius_profile_by_name() -> None:
    client = DummyClient()
    client.get_response = {
        "result": {
            "data": [
                {"name": "Other RADIUS", "radiusProfileId": "r-other"},
                {"name": "Home Networking Wi-Fi", "radiusProfileId": "6a0244454bc9cf648f0c1090"},
            ]
        }
    }
    resource = WiFiNetworksResource(client)

    profile_id = resource._lookup_radius_profile_id_by_name(
        site_id="s1",
        profile_name="Home Networking Wi-Fi",
    )

    assert profile_id == "6a0244454bc9cf648f0c1090"


def test_wifi_lookup_radius_profile_duplicate_names_raises() -> None:
    client = DummyClient()
    client.get_response = {
        "result": {
            "data": [
                {"name": "Home Networking Wi-Fi", "radiusProfileId": "r1"},
                {"name": "Home Networking Wi-Fi", "radiusProfileId": "r2"},
            ]
        }
    }
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="Multiple RADIUS profiles named"):
        resource._lookup_radius_profile_id_by_name(
            site_id="s1",
            profile_name="Home Networking Wi-Fi",
        )


def test_wifi_create_dpsk_from_radius_profile_name() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_dpsk_create(client)
    resource = WiFiNetworksResource(client)

    resource.create(
        site_id="s1",
        wlan_group="w1",
        type="dpsk",
        ssid="Resident",
        vlan=999,
        radius_profile_name="Home Networking Wi-Fi",
        nas_id="SITECODE",
    )

    assert client.get_calls[0][0].endswith("/sites/s1/profiles/radius")
    sent = cast(Dict[str, object], client.post_calls[0][1])
    assert sent["security"] == 5
    assert sent["pmfMode"] == 3
    ppsk = cast(Dict[str, object], sent["ppskSetting"])
    assert ppsk["radiusProfileId"] == "6a0244454bc9cf648f0c1090"
    assert ppsk["nasId"] == "SITECODE"
    assert ppsk["type"] == 2


def test_wifi_create_multicast_config_patches_after_post() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client, ssid_id="s-new")
    resource = WiFiNetworksResource(client)

    resource.create(
        site_id="s1",
        wlan_group="w1",
        type="open-isolated",
        ssid="Guest",
        vlan=98,
        multicast_config=_GUEST_MULTICAST,
    )

    assert len(client.post_calls) == 1
    assert len(client.patch_calls) == 1
    path, body = client.patch_calls[0]
    assert path.endswith("/wireless-network/wlans/w1/ssids/s-new/update-multicast-config")
    assert body == _GUEST_MULTICAST


def test_wifi_create_multicast_config_resolves_ssid_by_name_when_post_omits_id() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.post_response = {"ok": True}
    client.get_responses = [
        {"result": {"data": [{"ssidId": "s-listed", "name": "Guest"}]}},
    ]
    resource = WiFiNetworksResource(client)

    resource.create(
        site_id="s1",
        wlan_group="Corp",
        type="open-isolated",
        ssid="Guest",
        multicast_config=_GUEST_MULTICAST,
    )

    assert client.patch_calls[0][0].endswith("/ssids/s-listed/update-multicast-config")


def test_wifi_create_ppsk_local_multicast_config_patches() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_ppsk_local_create(client, ssid_id="s-new")
    resource = WiFiNetworksResource(client)

    resource.create(
        site_id="s1",
        wlan_group="w1",
        type="ppsk_local",
        ssid="Corporate",
        vlan=999,
        ppsk_profile_name="Services_PPSK_Profile",
        multicast_config=_SECURED_MULTICAST,
    )

    assert len(client.patch_calls) == 1
    path, body = client.patch_calls[0]
    assert path.endswith("/update-multicast-config")
    assert body["arpCastEnable"] is True
    assert body["filterEnable"] is False


def test_wifi_create_rejects_nested_multicast_wrapper() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client, ssid_id="s-new")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="flat UpdateSsidMultiCastOpenApiVO"):
        resource.create(
            site_id="s1",
            wlan_group="w1",
            type="open-isolated",
            ssid="Guest",
            multicast_config={"multiCast": _GUEST_MULTICAST},
        )


def test_wifi_update_multicast_config_by_name() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.get_response = {"result": {"data": [{"ssidId": "s9", "name": "Guest"}]}}
    resource = WiFiNetworksResource(client)

    resource.update_multicast_config(
        site_id="s1",
        wlan_group="Corp",
        name="Guest",
        multicast_config=_GUEST_MULTICAST,
    )

    assert client.patch_calls[0][0].endswith("/ssids/s9/update-multicast-config")
    assert cast(Dict[str, object], client.patch_calls[0][1])["filterMode"] == 15


_RATE_CONTROL: dict[str, object] = {
    "rate2gCtrlEnable": True,
    "lowerDensity2g": 12,
    "higherDensity2g": 54,
    "rate5gCtrlEnable": True,
    "lowerDensity5g": 12,
    "higherDensity5g": 54,
}


def test_wifi_update_rate_control_by_id() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    resource.update_rate_control(
        site_id="s1",
        wlan_group="w1",
        id="s9",
        rate_control=_RATE_CONTROL,
    )

    path, body = client.patch_calls[0]
    assert path.endswith("/wireless-network/wlans/w1/ssids/s9/update-rate-control")
    assert body == _RATE_CONTROL


def test_wifi_update_rate_control_by_name() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.get_response = {"result": {"data": [{"ssidId": "s9", "name": "Guest"}]}}
    resource = WiFiNetworksResource(client)

    resource.update_rate_control(
        site_id="s1",
        wlan_group="Corp",
        name="Guest",
        rate_control=_RATE_CONTROL,
    )

    assert client.patch_calls[0][0].endswith("/ssids/s9/update-rate-control")
    assert client.patch_calls[0][1] == _RATE_CONTROL


def test_wifi_create_rate_control_patches_after_post() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client, ssid_id="s-new")
    resource = WiFiNetworksResource(client)

    resource.create(
        site_id="s1",
        wlan_group="w1",
        type="open-isolated",
        ssid="Guest",
        vlan=98,
        rate_control=_RATE_CONTROL,
    )

    assert len(client.post_calls) == 1
    assert len(client.patch_calls) == 1
    path, body = client.patch_calls[0]
    assert path.endswith("/wireless-network/wlans/w1/ssids/s-new/update-rate-control")
    assert body == _RATE_CONTROL


def test_wifi_create_multicast_and_rate_control_patch_order() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client, ssid_id="s-new")
    resource = WiFiNetworksResource(client)

    resource.create(
        site_id="s1",
        wlan_group="w1",
        type="open-isolated",
        ssid="Guest",
        vlan=98,
        multicast_config=_GUEST_MULTICAST,
        rate_control=_RATE_CONTROL,
        rate_limit_profile_name="Default",
    )

    assert len(client.patch_calls) == 3
    assert client.patch_calls[0][0].endswith("/update-multicast-config")
    assert client.patch_calls[1][0].endswith("/update-rate-control")
    assert client.patch_calls[1][1] == _RATE_CONTROL
    assert client.patch_calls[2][0].endswith("/update-rate-limit")
    assert client.patch_calls[2][1] == _expected_rate_limit_patch_body()


def test_wifi_create_rejects_empty_rate_control() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client, ssid_id="s-new")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="non-empty dict"):
        resource.create(
            site_id="s1",
            wlan_group="w1",
            type="open-isolated",
            ssid="Guest",
            rate_control={},
        )


def test_wifi_create_rejects_nested_rate_control_wrapper() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client, ssid_id="s-new")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="flat UpdateSsidRateControlOpenApiVO"):
        resource.create(
            site_id="s1",
            wlan_group="w1",
            type="open-isolated",
            ssid="Guest",
            rate_control={"rateControl": _RATE_CONTROL},
        )


def test_wifi_update_rate_control_rejects_nested_wrapper() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="flat UpdateSsidRateControlOpenApiVO"):
        resource.update_rate_control(
            site_id="s1",
            wlan_group="w1",
            id="s9",
            rate_control={"rateControl": _RATE_CONTROL},
        )


def test_wifi_lookup_default_rate_limit_profile() -> None:
    client = DummyClient()
    client.get_response = {
        "result": {
            "data": [
                {"name": "Other", "profileId": "p-other"},
                {"name": "Default", "profileId": "p-default"},
            ]
        }
    }
    resource = WiFiNetworksResource(client)

    profile_id = resource._lookup_rate_limit_profile_id_by_name(site_id="s1", name="Default")

    assert profile_id == "p-default"


def test_wifi_lookup_rate_limit_profile_duplicate_names_raises() -> None:
    client = DummyClient()
    client.get_response = {
        "result": {
            "data": [
                {"name": "Default", "profileId": "p1"},
                {"name": "Default", "profileId": "p2"},
            ]
        }
    }
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="Multiple rate limit profiles"):
        resource._lookup_rate_limit_profile_id_by_name(site_id="s1", name="Default")


def test_wifi_update_rate_limit_by_name() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.get_responses = [
        _rate_limit_profiles_response(profile_id="p-default"),
        {"result": {"data": [{"ssidId": "s9", "name": "Guest"}]}},
    ]
    resource = WiFiNetworksResource(client)

    resource.update_rate_limit(site_id="s1", wlan_group="Corp", name="Guest", rate_limit_profile_name="Default")

    assert client.patch_calls[0][0].endswith("/ssids/s9/update-rate-limit")
    assert client.patch_calls[0][1] == _expected_rate_limit_patch_body("p-default")


def test_wifi_update_rate_limit_rejects_empty_name() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="rate_limit_profile_name must be a non-empty string"):
        resource.update_rate_limit(site_id="s1", wlan_group="w1", id="s9", rate_limit_profile_name="")


def test_wifi_create_skips_rate_limit_when_unset() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client, ssid_id="s-new", profile_id="p-default")
    resource = WiFiNetworksResource(client)

    resource.create(site_id="s1", wlan_group="w1", type="open", ssid="Plain")

    assert not any("/rate-limit-profiles" in c[0] for c in client.get_calls)
    assert not any(c[0].endswith("/update-rate-limit") for c in client.patch_calls)


def test_wifi_create_applies_rate_limit_profile_by_name() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client, ssid_id="s-new", profile_id="p-default")
    resource = WiFiNetworksResource(client)

    resource.create(
        site_id="s1",
        wlan_group="w1",
        type="open",
        ssid="Limited",
        rate_limit_profile_name="Default",
    )

    assert any("/rate-limit-profiles" in c[0] for c in client.get_calls)
    assert client.patch_calls[-1][0].endswith("/update-rate-limit")
    assert client.patch_calls[-1][1] == _expected_rate_limit_patch_body("p-default")


def test_wifi_create_partial_failure_raises_with_ssid_id() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.post_response = {"result": {"ssidId": "s-new"}}
    # multicast PATCH succeeds; rate-limit name lookup finds no profile and fails.
    client.get_response = {"result": {"data": []}}
    resource = WiFiNetworksResource(client)

    with pytest.raises(WiFiNetworkPartiallyConfiguredError) as excinfo:
        resource.create(
            site_id="s1",
            wlan_group="w1",
            type="open-isolated",
            ssid="Guest",
            multicast_config=_GUEST_MULTICAST,
            rate_limit_profile_name="Missing",
        )

    err = excinfo.value
    assert err.ssid_id == "s-new"
    assert err.failed_step == "update-rate-limit"
    assert err.completed_steps == ["update-multicast-config"]
    assert isinstance(err.__cause__, ValueError)
    assert client.patch_calls[0][0].endswith("/update-multicast-config")


def test_wifi_create_open_isolated_default_pmf_mode() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client)
    resource = WiFiNetworksResource(client)

    resource.create(site_id="s1", wlan_group="w1", type="open-isolated", ssid="Guest", vlan=98)

    sent = cast(Dict[str, object], client.post_calls[0][1])
    assert sent["pmfMode"] == 2
    assert sent["vlanSetting"]["customConfig"]["vlanPoolIds"] == "98"


def test_wifi_create_rejects_profile_id_with_ppsk_setting() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="ppsk_profile_name or ppsk_setting"):
        resource.create(
            site_id="s1",
            wlan_group="w1",
            type="ppsk_local",
            ssid="A",
            ppsk_profile_name="Services_PPSK_Profile",
            ppsk_setting={"ppskProfileId": "p2"},
        )


def test_wifi_create_dpsk_requires_nas_id_with_radius_profile() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="requires nas_id"):
        resource.create(
            site_id="s1",
            wlan_group="w1",
            type="dpsk",
            ssid="A",
            radius_profile_name="Home Networking Wi-Fi",
        )


def test_wifi_create_ppsk_local_security_four_both_settings() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client)
    resource = WiFiNetworksResource(client)

    resource.create(
        site_id="s1",
        wlan_group="w1",
        type="ppsk_local",
        ssid="Corp",
        psk="secret",
        ppsk_setting={"ppskProfileId": "prof1", "macFormat": 2, "type": 0},
    )

    sent = cast(Dict[str, object], client.post_calls[0][1])
    assert sent["security"] == 4
    assert isinstance(sent.get("pskSetting"), dict)
    assert isinstance(sent.get("ppskSetting"), dict)


def test_wifi_create_rejects_hotspot20() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="hotspot20"):
        resource.create(site_id="s1", wlan_group="w1", type="hotspot20", ssid="A")


def test_wifi_create_requires_type_specific_settings() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="type='psk' requires"):
        resource.create(site_id="s1", wlan_group="w1", type="psk", ssid="A")

    with pytest.raises(ValueError, match="type='dpsk' requires"):
        resource.create(site_id="s1", wlan_group="w1", type="dpsk", ssid="A")

    with pytest.raises(ValueError, match="type='aaa' requires"):
        resource.create(site_id="s1", wlan_group="w1", type="aaa", ssid="A")

    with pytest.raises(ValueError, match="type='ppsk_local' requires psk_setting"):
        resource.create(
            site_id="s1",
            wlan_group="w1",
            type="ppsk_local",
            ssid="A",
            ppsk_setting={"ppskProfileId": "p"},
        )

    with pytest.raises(ValueError, match="type='ppsk_local' requires ppsk_setting"):
        resource.create(site_id="s1", wlan_group="w1", type="ppsk_local", ssid="A", psk="x")


def test_wifi_create_name_only_matches_ruckus_style() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client)
    resource = WiFiNetworksResource(client)

    resource.create(site_id="s1", wlan_group="w1", type="open", name="OnlyName")

    sent = cast(Dict[str, object], client.post_calls[0][1])
    assert sent["name"] == "OnlyName"


def test_wifi_create_rejects_mismatched_name_and_ssid() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="identical"):
        resource.create(site_id="s1", wlan_group="w1", type="open", ssid="A", name="B")


def test_wifi_create_rejects_network_data_name() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="network_data must not include 'name'"):
        resource.create(
            site_id="s1",
            wlan_group="w1",
            type="open",
            ssid="SsidName",
            network_data={"name": "NetworkName"},
        )


def test_wifi_create_requires_broadcast_name() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="ssid' and/or 'name'"):
        resource.create(site_id="s1", wlan_group="w1", type="open")


def test_wifi_assign_to_ap_group_unchanged() -> None:
    client = DummyClient()
    resource = WiFiNetworksResource(client)
    resource.assign_to_ap_group(site_id="s1", wlan_id="w1", ap_group_id="g1")
    assert client.post_calls[0] == (
        "/openapi/v1/sites/s1/wlans/w1/ap-groups",
        {"wlanId": "w1", "apGroupId": "g1"},
    )


class OmadacPathDummyClient(DummyClient):
    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/omadac-1/")


def test_wifi_methods_use_api_path_rewrite() -> None:
    client = OmadacPathDummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.get_responses = [
        {"result": {"data": []}},
        _rate_limit_profiles_response(),
    ]
    client.post_response = {"result": {"ssidId": "s-new"}}
    resource = WiFiNetworksResource(client)

    resource.all(site_id="s1", wlan_group="w1")
    resource.create(
        site_id="s1",
        wlan_group="w1",
        type="open",
        ssid="GuestSSID",
        rate_limit_profile_name="Default",
    )

    assert client.get_calls[0][0] == "/openapi/v1/omadac-1/sites/s1/wireless-network/wlans/w1/ssids"
    assert client.post_calls[0][0] == "/openapi/v1/omadac-1/sites/s1/wireless-network/wlans/w1/ssids"
    assert any(c[0].endswith("/update-rate-limit") for c in client.patch_calls)
    assert any("/rate-limit-profiles" in c[0] for c in client.get_calls)


def test_wifi_create_open_works_without_security_blocks() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    _wire_post_create(client)
    resource = WiFiNetworksResource(client)
    result = resource.create(
        site_id="s1",
        wlan_group="w1",
        type="open",
        ssid="GuestSSID",
    )
    assert result == {"result": {"ssidId": "s-new"}}


def test_strip_ssid_detail_for_create_keeps_create_keys_only() -> None:
    detail = {
        "ssidId": "x",
        "name": "N",
        "security": 3,
        "band": 3,
        "pskSetting": {"versionPsk": 2},
        "clientRateLimit": {"profileId": "p"},
        "autoWanAccess": False,
    }
    stripped = strip_ssid_detail_for_create(detail)
    assert stripped == {"name": "N", "security": 3, "band": 3, "pskSetting": {"versionPsk": 2}}


def _ssid_detail_minimal(*, name: str = "N", ssid_id: str = "s1", security: int = 3) -> dict[str, object]:
    return {
        "ssidId": ssid_id,
        "band": 3,
        "broadcast": True,
        "enable11r": False,
        "guestNetEnable": False,
        "hidePwd": False,
        "mloEnable": False,
        "name": name,
        "pmfMode": 2,
        "security": security,
        "vlanEnable": False,
    }


def test_wifi_filter_by_ssid_matches_broadcast_name_field() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.get_response = {
        "result": {
            "data": [
                {"ssidId": "a", "name": "Guest", "security": 0},
                {"ssidId": "b", "name": "Staff", "security": 3},
            ]
        }
    }
    resource = WiFiNetworksResource(client)

    matched = resource.filter(site_id="s1", wlan_group="Corp", ssid="Guest")

    assert matched == [{"ssidId": "a", "name": "Guest", "security": 0}]
    assert client.get_calls[0][1] == {"page": 1, "pageSize": 1000, "searchKey": "Guest"}


def test_wifi_filter_combined_criteria_without_search_key_optimization() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.get_response = {
        "result": {
            "data": [
                {"ssidId": "a", "name": "Guest", "security": 0},
                {"ssidId": "b", "name": "Guest", "security": 3},
            ]
        }
    }
    resource = WiFiNetworksResource(client)

    matched = resource.filter(site_id="s1", wlan_group="Corp", name="Guest", security=3)

    assert matched == [{"ssidId": "b", "name": "Guest", "security": 3}]
    assert client.get_calls[0][1] == {"page": 1, "pageSize": 1000}


def test_wifi_filter_rejects_unknown_criterion() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.get_response = {"result": {"data": []}}
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="Unsupported filter criteria"):
        resource.filter(site_id="s1", wlan_group="Corp", foo="bar")


def test_wifi_filter_requires_at_least_one_criterion() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="at least one filter criterion"):
        resource.filter(site_id="s1", wlan_group="Corp")


def test_wifi_filter_rejects_mismatched_ssid_and_name_criteria() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    client.get_response = {"result": {"data": []}}
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="ssid' and 'name'"):
        resource.filter(site_id="s1", wlan_group="Corp", ssid="A", name="B")


def test_wifi_update_basic_config_patches_merged_payload() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    detail = _ssid_detail_minimal(name="Old", security=3)
    detail["pskSetting"] = {"securityKey": "x"}
    client.get_response = {"result": detail}
    resource = WiFiNetworksResource(client)

    result = resource.update_basic_config(site_id="s1", wlan_group="w1", id="s1", ssid="NewSSID")

    assert result == {"ok": True}
    assert len(client.get_calls) == 1
    path, body = client.patch_calls[0]
    assert path.endswith("/wireless-network/wlans/w1/ssids/s1/update-basic-config")
    sent = cast(Dict[str, object], body)
    assert sent["name"] == "NewSSID"
    assert sent["security"] == 3


def test_wifi_update_basic_config_by_name() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    detail = _ssid_detail_minimal(name="Guest", ssid_id="s9", security=0)
    client.get_responses = [
        {"result": {"data": [{"ssidId": "s9", "name": "Guest"}]}},
        {"result": detail},
    ]
    resource = WiFiNetworksResource(client)

    resource.update_basic_config(
        site_id="s1",
        wlan_group="Corp",
        name="Guest",
        network_data={"guestNetEnable": True},
    )

    assert client.patch_calls[0][0].endswith("/ssids/s9/update-basic-config")
    assert cast(Dict[str, object], client.patch_calls[0][1])["guestNetEnable"] is True


def test_ssid_detail_to_basic_config_patch_unknown_override_raises() -> None:
    detail = _ssid_detail_minimal()
    with pytest.raises(ValueError, match="Unknown override key"):
        ssid_detail_to_basic_config_patch(detail, {"notAField": 1})


def test_ssid_detail_to_basic_config_patch_missing_required_raises() -> None:
    with pytest.raises(ValueError, match="Missing required fields"):
        ssid_detail_to_basic_config_patch({"name": "only"})


def test_ssid_detail_to_basic_config_patch_ssid_alias() -> None:
    detail = _ssid_detail_minimal(name="A")
    out = ssid_detail_to_basic_config_patch(detail, {"ssid": "B"})
    assert out["name"] == "B"


def test_ssid_detail_to_basic_config_patch_rejects_conflicting_ssid_name_overrides() -> None:
    detail = _ssid_detail_minimal()
    with pytest.raises(ValueError, match="ssid' and 'name'"):
        ssid_detail_to_basic_config_patch(detail, {"ssid": "A", "name": "B"})
