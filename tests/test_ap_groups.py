from __future__ import annotations

from omada_client.resources.ap_groups import APGroupsResource


class DummyClient:
    def __init__(self) -> None:
        self.last = None

    def post(self, path: str, json=None):
        self.last = (path, json)
        return {"ok": True}


def test_create_ap_group() -> None:
    client = DummyClient()
    resource = APGroupsResource(client)

    result = resource.create(site_id="s1", group_data={"name": "APGroupA"})

    assert result == {"ok": True}
    assert client.last == ("/openapi/v1/sites/s1/ap-groups", {"name": "APGroupA"})


class OmadacPathDummyClient(DummyClient):
    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/omadac-1/")


def test_create_ap_group_uses_api_path_rewrite() -> None:
    client = OmadacPathDummyClient()
    resource = APGroupsResource(client)

    resource.create(site_id="s1", group_data={"name": "APGroupA"})

    assert client.last == ("/openapi/v1/omadac-1/sites/s1/ap-groups", {"name": "APGroupA"})
