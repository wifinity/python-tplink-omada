from __future__ import annotations

from omada_client.resources.sites import SitesResource


class DummyClient:
    def __init__(self) -> None:
        self.last_path = ""
        self.last_json = None

    def post(self, path: str, json):
        self.last_path = path
        self.last_json = json
        return {"ok": True}


def test_create_site() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    result = resource.create(name="SiteA", tz="UTC")

    assert result == {"ok": True}
    assert client.last_path == "/openapi/v1/sites"
    assert client.last_json["name"] == "SiteA"
    assert client.last_json["tz"] == "UTC"


class OmadacPathDummyClient(DummyClient):
    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/omadac-1/")


def test_create_site_uses_api_path_rewrite() -> None:
    client = OmadacPathDummyClient()
    resource = SitesResource(client)

    resource.create(name="SiteA")

    assert client.last_path == "/openapi/v1/omadac-1/sites"
