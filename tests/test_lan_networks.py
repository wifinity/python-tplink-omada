from __future__ import annotations

import pytest

from omada_client.exceptions import LanNetworkNotFoundError
from omada_client.resources.lan_networks import LanNetworksResource


class DummyClient:
    def __init__(self) -> None:
        self.get_response: dict = {}
        self.get_responses: list | None = None
        self.get_calls: list[tuple[str, object]] = []
        self.post_calls: list[tuple[str, object]] = []
        self.patch_calls: list[tuple[str, object]] = []
        self.delete_calls: list[str] = []

    def get(self, path: str, params=None):
        self.get_calls.append((path, params))
        if isinstance(self.get_responses, list) and self.get_responses:
            return self.get_responses.pop(0)
        return self.get_response

    def post(self, path: str, json=None):
        self.post_calls.append((path, json))
        return {"ok": True}

    def patch(self, path: str, json=None):
        self.patch_calls.append((path, json))
        return {"ok": True}

    def delete(self, path: str):
        self.delete_calls.append(path)
        return {"ok": True}


class ApiPathDummyClient(DummyClient):
    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/omadac-1/")


def _list_response(*networks):
    return {"result": {"data": list(networks)}}


def _net(vlan_id: int, name: str = "Test", network_id: str | None = None) -> dict:
    n: dict = {"vlan": vlan_id, "name": name, "dhcpSettingsVO": {"enable": False}}
    if network_id is not None:
        n["id"] = network_id
    return n


# ---------------------------------------------------------------------------
# all()
# ---------------------------------------------------------------------------


def test_all_returns_network_list() -> None:
    client = DummyClient()
    client.get_response = _list_response(_net(98, "guest", "net-1"))
    resource = LanNetworksResource(client)

    result = resource.all(site_id="s1")

    assert len(result) == 1
    assert result[0]["vlan"] == 98
    path, params = client.get_calls[0]
    assert path == "/openapi/v1/sites/s1/lan-networks"
    assert params == {"page": 1, "pageSize": 1000}


def test_all_pages_through_multiple_pages() -> None:
    """A site with more networks than one page holds must return every network.

    Regression: fetching only page 1 (pageSize cap) silently dropped the highest
    VLANs, so VLAN resolution failed for them with a misleading "no LAN network
    on the site" error. Uses a small page_size to keep the fixture cheap.
    """
    client = DummyClient()
    # Page 1 is full (2 items == page_size) so paging must continue; page 2 is
    # short (1 item) so paging stops after it.
    client.get_responses = [
        _list_response(_net(98, "guest", "net-1"), _net(99, "onboarding", "net-2")),
        _list_response(_net(2998, "home-2998", "net-3")),
    ]
    resource = LanNetworksResource(client)

    result = resource.all(site_id="s1", page_size=2)

    assert [n["vlan"] for n in result] == [98, 99, 2998]
    assert len(client.get_calls) == 2
    assert client.get_calls[0][1] == {"page": 1, "pageSize": 2}
    assert client.get_calls[1][1] == {"page": 2, "pageSize": 2}


def test_all_stops_when_final_page_is_exactly_full() -> None:
    """When the last page is exactly full, the next (empty) page terminates paging."""
    client = DummyClient()
    client.get_responses = [
        _list_response(_net(98, "guest", "net-1"), _net(99, "onboarding", "net-2")),
        {"result": {"data": []}},
    ]
    resource = LanNetworksResource(client)

    result = resource.all(site_id="s1", page_size=2)

    assert [n["vlan"] for n in result] == [98, 99]
    assert len(client.get_calls) == 2


def test_all_returns_empty_list_when_no_data() -> None:
    client = DummyClient()
    client.get_response = {"result": {"data": []}}
    resource = LanNetworksResource(client)

    assert resource.all(site_id="s1") == []


def test_all_handles_missing_result_key() -> None:
    client = DummyClient()
    client.get_response = {}
    resource = LanNetworksResource(client)

    assert resource.all(site_id="s1") == []


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------


def test_get_by_network_id_returns_result_dict() -> None:
    client = DummyClient()
    client.get_response = {"result": {"vlan": 98, "id": "net-1", "name": "guest"}}
    resource = LanNetworksResource(client)

    result = resource.get(site_id="s1", network_id="net-1")

    assert result["id"] == "net-1"
    assert client.get_calls[0][0] == "/openapi/v1/sites/s1/lan-networks/net-1"


def test_get_by_network_id_raises_when_result_missing() -> None:
    client = DummyClient()
    client.get_response = {}
    resource = LanNetworksResource(client)

    with pytest.raises(LanNetworkNotFoundError, match="net-1"):
        resource.get(site_id="s1", network_id="net-1")


def test_get_by_vlan_id_returns_matching_network() -> None:
    client = DummyClient()
    client.get_response = _list_response(
        _net(99, "onboarding", "net-0"),
        _net(98, "guest", "net-1"),
    )
    resource = LanNetworksResource(client)

    result = resource.get(site_id="s1", vlan_id=98)

    assert result["vlan"] == 98
    assert result["name"] == "guest"


def test_get_by_vlan_id_raises_when_not_found() -> None:
    client = DummyClient()
    client.get_response = _list_response(_net(99, "onboarding", "net-0"))
    resource = LanNetworksResource(client)

    with pytest.raises(LanNetworkNotFoundError, match="VLAN 98"):
        resource.get(site_id="s1", vlan_id=98)


def test_get_rejects_invalid_selector_combinations() -> None:
    client = DummyClient()
    resource = LanNetworksResource(client)

    with pytest.raises(ValueError, match="Provide exactly one"):
        resource.get(site_id="s1")

    with pytest.raises(ValueError, match="Provide exactly one"):
        resource.get(site_id="s1", network_id="net-1", vlan_id=98)


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


def test_create_posts_correct_payload() -> None:
    client = DummyClient()
    resource = LanNetworksResource(client)

    resource.create(site_id="s1", name="guest", vlan_id=98)

    assert len(client.post_calls) == 1
    path, payload = client.post_calls[0]
    assert path == "/openapi/v1/sites/s1/networks/confirm"
    lan = payload["lanNetwork"]
    assert lan["name"] == "guest"
    assert lan["vlan"] == 98
    assert lan["vlanType"] == 0
    assert lan["deviceType"] == 3
    assert lan["igmpSnoopEnable"] is False
    assert payload["deviceConfig"] == {"deviceList": []}


def test_create_dhcp_device_default_is_external() -> None:
    client = DummyClient()
    resource = LanNetworksResource(client)

    resource.create(site_id="s1", name="guest", vlan_id=98)

    _, payload = client.post_calls[0]
    assert payload["lanNetwork"]["deviceType"] == 3


def test_create_dhcp_device_gateway() -> None:
    client = DummyClient()
    resource = LanNetworksResource(client)

    resource.create(site_id="s1", name="guest", vlan_id=98, dhcp_device="gateway")

    _, payload = client.post_calls[0]
    assert payload["lanNetwork"]["deviceType"] == 1


def test_create_raises_on_empty_name() -> None:
    client = DummyClient()
    resource = LanNetworksResource(client)

    with pytest.raises(ValueError, match="name must be a non-empty string"):
        resource.create(site_id="s1", name="", vlan_id=98)


# ---------------------------------------------------------------------------
# update()
# ---------------------------------------------------------------------------


def _existing_net(vlan_id: int = 98, name: str = "old-name", dhcp_enable: bool = False) -> dict:
    return {
        "result": {
            "id": "net-1",
            "vlan": vlan_id,
            "name": name,
            "purpose": 0,
            "igmpSnoopEnable": False,
            "dhcpSettingsVO": {"enable": dhcp_enable},
        }
    }


def test_update_by_network_id_merges_over_existing() -> None:
    client = DummyClient()
    client.get_response = _existing_net(name="old-name")
    resource = LanNetworksResource(client)

    resource.update(site_id="s1", network_id="net-1", name="renamed")

    assert len(client.patch_calls) == 1
    path, payload = client.patch_calls[0]
    assert path == "/openapi/v1/sites/s1/lan-networks/net-1"
    assert payload["name"] == "renamed"
    assert payload["purpose"] == 0
    assert payload["igmpSnoopEnable"] is False


def test_update_by_vlan_id_resolves_network_id() -> None:
    client = DummyClient()
    client.get_response = _list_response(_net(98, "old-name", "net-1"))
    resource = LanNetworksResource(client)

    resource.update(site_id="s1", vlan_id=98, name="renamed")

    path, payload = client.patch_calls[0]
    assert path == "/openapi/v1/sites/s1/lan-networks/net-1"
    assert payload["name"] == "renamed"


def test_update_without_name_preserves_existing_name() -> None:
    client = DummyClient()
    client.get_response = _existing_net(name="keep-me")
    resource = LanNetworksResource(client)

    resource.update(site_id="s1", network_id="net-1", dhcp_server_enabled=False)

    _, payload = client.patch_calls[0]
    assert payload["name"] == "keep-me"


def test_update_dhcp_sets_enable_field() -> None:
    client = DummyClient()
    client.get_response = _existing_net(dhcp_enable=True)
    resource = LanNetworksResource(client)

    resource.update(site_id="s1", network_id="net-1", dhcp_server_enabled=False)

    _, payload = client.patch_calls[0]
    assert payload["dhcpSettingsVO"]["enable"] is False


def test_update_name_and_dhcp_together() -> None:
    client = DummyClient()
    client.get_response = _existing_net()
    resource = LanNetworksResource(client)

    resource.update(site_id="s1", network_id="net-1", name="guest", dhcp_server_enabled=False)

    _, payload = client.patch_calls[0]
    assert payload["name"] == "guest"
    assert payload["dhcpSettingsVO"]["enable"] is False


def test_update_rejects_invalid_selector_combinations() -> None:
    client = DummyClient()
    resource = LanNetworksResource(client)

    with pytest.raises(ValueError, match="Provide exactly one"):
        resource.update(site_id="s1", name="x")

    with pytest.raises(ValueError, match="Provide exactly one"):
        resource.update(site_id="s1", network_id="net-1", vlan_id=98, name="x")


# ---------------------------------------------------------------------------
# vlan_id_to_network_id()
# ---------------------------------------------------------------------------


def test_vlan_id_to_network_id_builds_correct_dict() -> None:
    client = DummyClient()
    client.get_response = _list_response(
        _net(98, "guest", "net-1"),
        _net(99, "onboarding", "net-2"),
    )
    resource = LanNetworksResource(client)

    result = resource.vlan_id_to_network_id(site_id="s1")

    assert result == {98: "net-1", 99: "net-2"}


def test_vlan_id_to_network_id_skips_entries_missing_id_or_vlan() -> None:
    client = DummyClient()
    client.get_response = _list_response(
        {"name": "no-id", "vlan": 98},
        {"name": "no-vlan", "id": "net-x"},
        _net(99, "onboarding", "net-2"),
    )
    resource = LanNetworksResource(client)

    result = resource.vlan_id_to_network_id(site_id="s1")

    assert result == {99: "net-2"}


def test_vlan_id_to_network_id_returns_empty_on_no_networks() -> None:
    client = DummyClient()
    client.get_response = {"result": {"data": []}}
    resource = LanNetworksResource(client)

    assert resource.vlan_id_to_network_id(site_id="s1") == {}


# ---------------------------------------------------------------------------
# API path rewriting
# ---------------------------------------------------------------------------


def test_all_uses_api_path_rewrite() -> None:
    client = ApiPathDummyClient()
    client.get_response = _list_response()
    resource = LanNetworksResource(client)

    resource.all(site_id="s1")

    assert client.get_calls[0][0] == "/openapi/v1/omadac-1/sites/s1/lan-networks"


def test_create_uses_api_path_rewrite() -> None:
    client = ApiPathDummyClient()
    resource = LanNetworksResource(client)

    resource.create(site_id="s1", name="guest", vlan_id=98)

    assert client.post_calls[0][0] == "/openapi/v1/omadac-1/sites/s1/networks/confirm"


def test_update_uses_api_path_rewrite() -> None:
    client = ApiPathDummyClient()
    client.get_response = {"result": {"id": "net-1", "vlan": 98, "name": "old", "purpose": 0, "igmpSnoopEnable": False}}
    resource = LanNetworksResource(client)

    resource.update(site_id="s1", network_id="net-1", name="renamed")

    assert client.patch_calls[0][0] == "/openapi/v1/omadac-1/sites/s1/lan-networks/net-1"


def test_get_by_network_id_uses_api_path_rewrite() -> None:
    client = ApiPathDummyClient()
    client.get_response = {"result": {"vlan": 98, "id": "net-1"}}
    resource = LanNetworksResource(client)

    resource.get(site_id="s1", network_id="net-1")

    assert client.get_calls[0][0] == "/openapi/v1/omadac-1/sites/s1/lan-networks/net-1"


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------


def test_delete_by_network_id_sends_correct_path() -> None:
    client = DummyClient()
    resource = LanNetworksResource(client)

    resource.delete(site_id="s1", network_id="net-1")

    assert client.delete_calls == ["/openapi/v1/sites/s1/lan-networks/net-1"]


def test_delete_by_vlan_id_resolves_network_id() -> None:
    client = DummyClient()
    client.get_response = _list_response(_net(98, "guest", "net-1"))
    resource = LanNetworksResource(client)

    resource.delete(site_id="s1", vlan_id=98)

    assert client.delete_calls == ["/openapi/v1/sites/s1/lan-networks/net-1"]


def test_delete_rejects_invalid_selector_combinations() -> None:
    client = DummyClient()
    resource = LanNetworksResource(client)

    with pytest.raises(ValueError, match="Provide exactly one"):
        resource.delete(site_id="s1")

    with pytest.raises(ValueError, match="Provide exactly one"):
        resource.delete(site_id="s1", network_id="net-1", vlan_id=98)


def test_delete_uses_api_path_rewrite() -> None:
    client = ApiPathDummyClient()
    resource = LanNetworksResource(client)

    resource.delete(site_id="s1", network_id="net-1")

    assert client.delete_calls == ["/openapi/v1/omadac-1/sites/s1/lan-networks/net-1"]
