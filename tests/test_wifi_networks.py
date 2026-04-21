from __future__ import annotations

from omada_client.resources.wifi_networks import WiFiNetworksResource


class DummyClient:
    def __init__(self) -> None:
        self.calls = []

    def post(self, path: str, json=None):
        self.calls.append((path, json))
        return {"ok": True}


def test_wifi_create_and_assign() -> None:
    client = DummyClient()
    resource = WiFiNetworksResource(client)

    resource.create("s1", {"name": "Corp"})
    resource.assign_to_ap_group("s1", "w1", "g1")

    assert client.calls[0] == ("/openapi/v1/sites/s1/wlans", {"name": "Corp"})
    assert client.calls[1] == (
        "/openapi/v1/sites/s1/wlans/w1/ap-groups",
        {"wlanId": "w1", "apGroupId": "g1"},
    )


class OmadacPathDummyClient(DummyClient):
    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/omadac-1/")


def test_wifi_create_and_assign_use_api_path_rewrite() -> None:
    client = OmadacPathDummyClient()
    resource = WiFiNetworksResource(client)

    resource.create("s1", {"name": "Corp"})
    resource.assign_to_ap_group("s1", "w1", "g1")

    assert client.calls[0] == ("/openapi/v1/omadac-1/sites/s1/wlans", {"name": "Corp"})
    assert client.calls[1] == (
        "/openapi/v1/omadac-1/sites/s1/wlans/w1/ap-groups",
        {"wlanId": "w1", "apGroupId": "g1"},
    )
