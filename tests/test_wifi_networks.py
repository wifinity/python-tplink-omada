from __future__ import annotations

from typing import Dict, cast

import pytest

from omada_client.resources.wifi_networks import WiFiNetworksResource


class DummyClient:
    def __init__(self) -> None:
        self.get_calls: list[tuple[str, object]] = []
        self.post_calls: list[tuple[str, object]] = []
        self.delete_calls: list[tuple[str, object]] = []
        self.get_response = {"ok": True}
        self.get_responses: list[dict[str, object]] | None = None
        self.post_response = {"ok": True}
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
    resource = WiFiNetworksResource(client)

    resource.create(
        site_id="s1",
        wlan_group="w1",
        type="dpsk",
        ssid="GuestSSID",
        ppsk_setting={"radiusId": "r1"},
    )

    sent = cast(Dict[str, object], client.post_calls[0][1])
    assert sent["security"] == 5
    assert "ppskSetting" in sent


def test_wifi_create_maps_vlan_shortcut_to_vlan_enable_and_vlan_id() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
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
    assert sent["vlanId"] == 99
    assert "vlan" not in sent


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


def test_wifi_create_rejects_unsupported_guest_and_hotspot20() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="Unsupported Wi-Fi type 'guest'"):
        resource.create(site_id="s1", wlan_group="w1", type="guest", ssid="A")

    with pytest.raises(ValueError, match="Unsupported Wi-Fi type 'hotspot20'"):
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


def test_wifi_create_rejects_name_in_kwargs_or_network_data() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)

    with pytest.raises(ValueError, match="name is not accepted; set ssid only"):
        resource.create(site_id="s1", wlan_group="w1", type="open", ssid="SsidName", name="NetworkName")

    with pytest.raises(ValueError, match="network_data must not include 'name'"):
        resource.create(
            site_id="s1",
            wlan_group="w1",
            type="open",
            ssid="SsidName",
            network_data={"name": "NetworkName"},
        )


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
    client.get_response = {"result": {"data": []}}
    resource = WiFiNetworksResource(client)

    resource.all(site_id="s1", wlan_group="w1")
    resource.create(
        site_id="s1",
        wlan_group="w1",
        type="open",
        ssid="GuestSSID",
    )

    assert client.get_calls[0][0] == "/openapi/v1/omadac-1/sites/s1/wireless-network/wlans/w1/ssids"
    assert client.post_calls[0][0] == "/openapi/v1/omadac-1/sites/s1/wireless-network/wlans/w1/ssids"


def test_wifi_create_open_works_without_security_blocks() -> None:
    client = DummyClient()
    _wire_wlan_group(client, group_id="w1", group_name="Corp")
    resource = WiFiNetworksResource(client)
    result = resource.create(
        site_id="s1",
        wlan_group="w1",
        type="open",
        ssid="GuestSSID",
    )
    assert result == {"ok": True}
