from __future__ import annotations

from omada_client.resources.devices import DevicesResource


class DummyClient:
    def __init__(self) -> None:
        self.calls = []

    def post(self, path: str, json=None):
        self.calls.append(("POST", path, json))
        return {"ok": True}

    def delete(self, path: str, json=None):
        self.calls.append(("DELETE", path, json))
        return {"ok": True}

    def get(self, path: str):
        self.calls.append(("GET", path, None))
        return {"status": "online"}


def test_device_workflow_calls_expected_paths() -> None:
    client = DummyClient()
    resource = DevicesResource(client)

    resource.register("s1", {"sn": "abc"})
    resource.remove("s1", ["d1"])
    resource.send_config("s1", "d1", {"k": "v"})
    status = resource.status("s1", "d1")

    assert status == {"status": "online"}
    assert client.calls[0] == ("POST", "/openapi/v1/sites/s1/devices", {"sn": "abc"})
    assert client.calls[1] == ("DELETE", "/openapi/v1/sites/s1/devices", {"deviceIds": ["d1"]})
    assert client.calls[2] == ("POST", "/openapi/v1/sites/s1/devices/d1/config", {"k": "v"})
    assert client.calls[3] == ("GET", "/openapi/v1/sites/s1/devices/d1/status", None)


class OmadacPathDummyClient(DummyClient):
    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/omadac-1/")


def test_device_workflow_uses_api_path_rewrite() -> None:
    client = OmadacPathDummyClient()
    resource = DevicesResource(client)

    resource.register("s1", {"sn": "abc"})
    resource.remove("s1", ["d1"])
    resource.send_config("s1", "d1", {"k": "v"})
    resource.status("s1", "d1")

    assert client.calls[0] == ("POST", "/openapi/v1/omadac-1/sites/s1/devices", {"sn": "abc"})
    assert client.calls[1] == ("DELETE", "/openapi/v1/omadac-1/sites/s1/devices", {"deviceIds": ["d1"]})
    assert client.calls[2] == ("POST", "/openapi/v1/omadac-1/sites/s1/devices/d1/config", {"k": "v"})
    assert client.calls[3] == ("GET", "/openapi/v1/omadac-1/sites/s1/devices/d1/status", None)
