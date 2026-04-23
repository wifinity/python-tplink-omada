from __future__ import annotations

import pytest

from omada_client.exceptions import WLANGroupNotFoundError
from omada_client.resources.wlan_groups import WLANGroupsResource


class DummyClient:
    def __init__(self) -> None:
        self.last_path = ""
        self.last_params = None
        self.last_json = None
        self.get_response = {"ok": True}
        self.get_responses = None
        self.get_calls: list[tuple[str, object]] = []
        self.delete_calls: list[str] = []

    def post(self, path: str, json=None):
        self.last_path = path
        self.last_json = json
        return {"ok": True}

    def get(self, path: str, params=None):
        self.last_path = path
        self.last_params = params
        self.get_calls.append((path, params))
        if isinstance(self.get_responses, list) and self.get_responses:
            return self.get_responses.pop(0)
        return self.get_response

    def delete(self, path: str, json=None):
        self.last_path = path
        self.last_json = json
        self.delete_calls.append(path)
        return {"ok": True}


def test_all_wlan_groups_returns_result_data_list() -> None:
    client = DummyClient()
    client.get_response = {"result": {"data": [{"wlanId": "w1", "name": "Default"}]}}
    resource = WLANGroupsResource(client)

    result = resource.all(site_id="s1")

    assert result == [{"wlanId": "w1", "name": "Default"}]
    assert client.last_path == "/openapi/v1/sites/s1/wireless-network/wlans"
    assert client.last_params is None


def test_all_wlan_groups_passes_query_params() -> None:
    client = DummyClient()
    client.get_response = {"result": {"data": []}}
    resource = WLANGroupsResource(client)

    resource.all(site_id="s1", params={"searchKey": "Corp", "page": 2})

    assert client.last_path == "/openapi/v1/sites/s1/wireless-network/wlans"
    assert client.last_params == {"searchKey": "Corp", "page": 2}


def test_create_wlan_group_calls_expected_path() -> None:
    client = DummyClient()
    resource = WLANGroupsResource(client)

    result = resource.create(site_id="s1", group_data={"name": "Corp"})

    assert result == {"ok": True}
    assert client.last_path == "/openapi/v1/sites/s1/wireless-network/wlans"
    assert client.last_json == {"name": "Corp", "clone": False}


def test_create_wlan_group_accepts_name_parameter() -> None:
    client = DummyClient()
    resource = WLANGroupsResource(client)

    result = resource.create(site_id="s1", name="Corp")

    assert result == {"ok": True}
    assert client.last_path == "/openapi/v1/sites/s1/wireless-network/wlans"
    assert client.last_json == {"name": "Corp", "clone": False}


def test_create_wlan_group_name_parameter_overrides_group_data_name() -> None:
    client = DummyClient()
    resource = WLANGroupsResource(client)

    resource.create(site_id="s1", name="Corp", group_data={"name": "OldName", "foo": "bar"})

    assert client.last_json == {"name": "Corp", "foo": "bar", "clone": False}


def test_create_wlan_group_preserves_explicit_clone_value() -> None:
    client = DummyClient()
    resource = WLANGroupsResource(client)

    resource.create(site_id="s1", name="Corp", group_data={"clone": True, "clonedWlanId": "w1"})

    assert client.last_json == {"name": "Corp", "clone": True, "clonedWlanId": "w1"}


def test_create_wlan_group_requires_name_from_name_or_group_data() -> None:
    client = DummyClient()
    resource = WLANGroupsResource(client)

    with pytest.raises(ValueError, match="name is required"):
        resource.create(site_id="s1")

    with pytest.raises(ValueError, match="name is required"):
        resource.create(site_id="s1", group_data={"foo": "bar"})


def test_get_wlan_group_by_id_uses_group_endpoint() -> None:
    client = DummyClient()
    client.get_response = {"result": {"wlanId": "w1", "name": "Default"}}
    resource = WLANGroupsResource(client)

    result = resource.get(site_id="s1", id="w1")

    assert result == {"wlanId": "w1", "name": "Default"}
    assert client.last_path == "/openapi/v1/sites/s1/wireless-network/wlans/w1"
    assert client.last_params is None


def test_get_wlan_group_by_name_uses_list_search_and_exact_match() -> None:
    client = DummyClient()
    client.get_response = {
        "result": {
            "data": [
                {"wlanId": "w1", "name": "Default"},
                {"wlanId": "w2", "name": "Guest"},
            ]
        }
    }
    resource = WLANGroupsResource(client)

    result = resource.get(site_id="s1", name="Default")

    assert result == {"wlanId": "w1", "name": "Default"}
    assert client.get_calls[0] == (
        "/openapi/v1/sites/s1/wireless-network/wlans",
        {"searchKey": "Default"},
    )


def test_get_wlan_group_rejects_invalid_selector_combinations() -> None:
    client = DummyClient()
    resource = WLANGroupsResource(client)

    with pytest.raises(ValueError, match="Provide exactly one of 'id' or 'name'"):
        resource.get(site_id="s1")

    with pytest.raises(ValueError, match="Provide exactly one of 'id' or 'name'"):
        resource.get(site_id="s1", id="w1", name="Default")


def test_get_wlan_group_by_name_raises_when_not_found() -> None:
    client = DummyClient()
    client.get_response = {"result": {"data": [{"wlanId": "w2", "name": "Guest"}]}}
    resource = WLANGroupsResource(client)

    with pytest.raises(WLANGroupNotFoundError, match="WLAN group with name 'Default' was not found"):
        resource.get(site_id="s1", name="Default")


def test_get_wlan_group_by_name_raises_when_multiple_exact_matches() -> None:
    client = DummyClient()
    client.get_response = {
        "result": {
            "data": [
                {"wlanId": "w1", "name": "Default"},
                {"wlanId": "w2", "name": "Default"},
            ]
        }
    }
    resource = WLANGroupsResource(client)

    with pytest.raises(ValueError, match="Multiple WLAN groups found with name 'Default'"):
        resource.get(site_id="s1", name="Default")


def test_delete_wlan_group_by_id_uses_group_endpoint() -> None:
    client = DummyClient()
    resource = WLANGroupsResource(client)

    result = resource.delete(site_id="s1", id="w1")

    assert result == {"ok": True}
    assert client.delete_calls[0] == "/openapi/v1/sites/s1/wireless-network/wlans/w1"


def test_delete_wlan_group_by_name_resolves_and_deletes_by_wlan_id() -> None:
    client = DummyClient()
    client.get_response = {"result": {"data": [{"wlanId": "w1", "name": "Default"}]}}
    resource = WLANGroupsResource(client)

    result = resource.delete(site_id="s1", name="Default")

    assert result == {"ok": True}
    assert client.get_calls[0] == (
        "/openapi/v1/sites/s1/wireless-network/wlans",
        {"searchKey": "Default"},
    )
    assert client.delete_calls[0] == "/openapi/v1/sites/s1/wireless-network/wlans/w1"


def test_delete_wlan_group_rejects_invalid_selector_combinations() -> None:
    client = DummyClient()
    resource = WLANGroupsResource(client)

    with pytest.raises(ValueError, match="Provide exactly one of 'id' or 'name'"):
        resource.delete(site_id="s1")

    with pytest.raises(ValueError, match="Provide exactly one of 'id' or 'name'"):
        resource.delete(site_id="s1", id="w1", name="Default")


def test_delete_wlan_group_by_name_raises_when_wlan_id_missing() -> None:
    client = DummyClient()
    client.get_response = {"result": {"data": [{"name": "Default"}]}}
    resource = WLANGroupsResource(client)

    with pytest.raises(ValueError, match="Matched WLAN group 'Default' does not include a valid wlanId"):
        resource.delete(site_id="s1", name="Default")


class OmadacPathDummyClient(DummyClient):
    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/omadac-1/")


def test_wlan_group_methods_use_api_path_rewrite() -> None:
    client = OmadacPathDummyClient()
    client.get_responses = [
        {"result": {"data": [{"wlanId": "w1", "name": "Default"}]}},
        {"result": {"data": [{"wlanId": "w1", "name": "Default"}]}},
    ]
    client.get_response = {"result": {"wlanId": "w1", "name": "Default"}}
    resource = WLANGroupsResource(client)

    resource.all(site_id="s1")
    assert client.last_path == "/openapi/v1/omadac-1/sites/s1/wireless-network/wlans"

    resource.create(site_id="s1", name="Corp")
    assert client.last_path == "/openapi/v1/omadac-1/sites/s1/wireless-network/wlans"

    resource.get(site_id="s1", name="Default")
    assert client.get_calls[1] == (
        "/openapi/v1/omadac-1/sites/s1/wireless-network/wlans",
        {"searchKey": "Default"},
    )

    resource.get(site_id="s1", id="w1")
    assert client.last_path == "/openapi/v1/omadac-1/sites/s1/wireless-network/wlans/w1"

    resource.delete(site_id="s1", id="w1")
    assert client.delete_calls[0] == "/openapi/v1/omadac-1/sites/s1/wireless-network/wlans/w1"
