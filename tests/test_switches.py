from __future__ import annotations

from omada_client.exceptions import DeviceNotFoundError
from omada_client.resources.switches import SwitchesResource


class DummyDevicesResource:
    def __init__(self) -> None:
        self.calls = []

    def list(self, *, site_id: str, page: int = 1, page_size: int = 1000, **params):
        self.calls.append(("list", site_id, page, page_size, params))
        search_key = params.get("searchKey")
        if search_key == "AA-BB-CC-DD-EE-FF":
            return {"result": {"data": [{"mac": search_key, "name": "SW-1", "status": 1, "detailStatus": 14}]}}
        if search_key == "SW-1":
            return {"result": {"data": [{"mac": "AA-BB-CC-DD-EE-FF", "name": "SW-1", "status": 1, "detailStatus": 14}]}}
        if search_key == "UNKNOWN-SW":
            return {
                "result": {
                    "data": [{"mac": "AA-BB-CC-DD-EE-99", "name": "UNKNOWN-SW", "status": 99, "detailStatus": 999}]
                }
            }
        if search_key == "DUPLICATE":
            return {
                "result": {
                    "data": [
                        {"mac": "AA-BB-CC-DD-EE-01", "name": "DUPLICATE"},
                        {"mac": "AA-BB-CC-DD-EE-02", "name": "DUPLICATE"},
                    ]
                }
            }
        return {"items": []}

    def add_by_device_key(
        self,
        *,
        site_id: str,
        device_key: str,
        name: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        self.calls.append(("add_by_device_key", site_id, device_key, name, username, password))
        return {"ok": True}

    def start_adopt(
        self,
        *,
        site_id: str,
        mac: str,
        username: str | None = None,
        password: str | None = None,
    ):
        self.calls.append(("start_adopt", site_id, mac, username, password))
        return {"started": True}

    def check_adopt(self, *, site_id: str, mac: str):
        self.calls.append(("check_adopt", site_id, mac))
        return {"result": {"adoptErrorCode": 0, "adoptErrorMeaning": "Adopt Device Success"}}

    def delete(self, *, site_id: str, mac: str):
        self.calls.append(("delete", site_id, mac))
        return {"forgotten": True}


class DummyHttpClient:
    """Minimal HTTP client stub for testing port methods directly."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict]] = []
        self._get_response: dict = {}
        self._post_response: dict = {}

    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/OMADACID/")

    def get(self, url: str, **kwargs) -> dict:
        self.requests.append(("GET", url, kwargs))
        return self._get_response

    def post(self, url: str, **kwargs) -> dict:
        self.requests.append(("POST", url, kwargs))
        return self._post_response

    def put(self, url: str, **kwargs) -> dict:
        self.requests.append(("PUT", url, kwargs))
        return {"ok": True}

    def patch(self, url: str, **kwargs) -> dict:
        self.requests.append(("PATCH", url, kwargs))
        return {"ok": True}


class DummyClient:
    def __init__(self) -> None:
        self.devices = DummyDevicesResource()


def test_switches_resource_delegates_to_devices_with_switch_options() -> None:
    client = DummyClient()
    resource = SwitchesResource(client)

    listed = resource.all(site_id="s1", page=2, page_size=50, searchKey="sw")
    by_mac = resource.get_by_mac(site_id="s1", mac="aa:bb:cc:dd:ee:ff")
    by_name = resource.get_by_name(site_id="s1", name="SW-1")
    created = resource.create(
        site_id="s1",
        device_key="ZTP-DEVICE-KEY",
        name="SW-1",
        username="admin",
        password="secret",
    )
    started_adopt = resource.start_adopt(
        site_id="s1",
        mac="aa:bb:cc:dd:ee:ff",
        username="admin",
        password="secret",
    )
    checked_adopt = resource.check_adopt(site_id="s1", mac="aa:bb:cc:dd:ee:ff")
    deleted = resource.delete(site_id="s1", mac="aa:bb:cc:dd:ee:ff")

    assert listed == {"items": []}
    assert by_mac == {
        "mac": "AA-BB-CC-DD-EE-FF",
        "name": "SW-1",
        "status": 1,
        "detailStatus": 14,
        "statusMeaning": "Connected",
        "detailStatusMeaning": "Connected",
    }
    assert by_name == {
        "mac": "AA-BB-CC-DD-EE-FF",
        "name": "SW-1",
        "status": 1,
        "detailStatus": 14,
        "statusMeaning": "Connected",
        "detailStatusMeaning": "Connected",
    }
    assert created == {"ok": True}
    assert started_adopt == {"started": True}
    assert checked_adopt == {"result": {"adoptErrorCode": 0, "adoptErrorMeaning": "Adopt Device Success"}}
    assert deleted == {"forgotten": True}

    assert client.devices.calls[0] == ("list", "s1", 2, 50, {"deviceType": "switch", "searchKey": "sw"})
    assert client.devices.calls[1] == (
        "list",
        "s1",
        1,
        1000,
        {"searchKey": "AA-BB-CC-DD-EE-FF", "deviceType": "switch"},
    )
    assert client.devices.calls[2] == ("list", "s1", 1, 1000, {"searchKey": "SW-1", "deviceType": "switch"})
    assert client.devices.calls[3] == ("add_by_device_key", "s1", "ZTP-DEVICE-KEY", "SW-1", "admin", "secret")
    assert client.devices.calls[4] == ("start_adopt", "s1", "aa:bb:cc:dd:ee:ff", "admin", "secret")
    assert client.devices.calls[5] == ("check_adopt", "s1", "aa:bb:cc:dd:ee:ff")
    assert client.devices.calls[6] == ("delete", "s1", "AA-BB-CC-DD-EE-FF")


def test_switches_resource_rejects_invalid_mac() -> None:
    client = DummyClient()
    resource = SwitchesResource(client)

    try:
        resource.get_by_mac(site_id="s1", mac="bad-mac")
        assert False, "Expected ValueError for invalid MAC"
    except ValueError as exc:
        assert "Invalid MAC address" in str(exc)

    assert client.devices.calls == []


def test_switches_resource_get_by_name_not_found_and_duplicate() -> None:
    client = DummyClient()
    resource = SwitchesResource(client)

    try:
        resource.get_by_name(site_id="s1", name="missing")
        assert False, "Expected ValueError for missing switch name"
    except ValueError as exc:
        assert "not found" in str(exc)

    try:
        resource.get_by_name(site_id="s1", name="DUPLICATE")
        assert False, "Expected ValueError for duplicate switch names"
    except ValueError as exc:
        assert "Multiple switches named 'DUPLICATE'" in str(exc)


def test_switches_resource_get_by_mac_not_found_raises_device_not_found() -> None:
    client = DummyClient()
    resource = SwitchesResource(client)

    try:
        resource.get_by_mac(site_id="s1", mac="aa:bb:cc:dd:ee:00")
        assert False, "Expected DeviceNotFoundError for missing switch MAC"
    except DeviceNotFoundError as exc:
        assert "not found" in str(exc)


def test_switches_resource_applies_unknown_status_meaning_fallbacks() -> None:
    client = DummyClient()
    resource = SwitchesResource(client)

    by_name = resource.get_by_name(site_id="s1", name="UNKNOWN-SW")

    assert by_name["statusMeaning"] == "Unknown status: 99"
    assert by_name["detailStatusMeaning"] == "Unknown detailStatus: 999"


def test_get_ports_returns_port_list_for_matching_switch() -> None:
    http = DummyHttpClient()
    http._post_response = {
        "result": [
            {
                "mac": "AA-BB-CC-DD-EE-FF",
                "ports": [
                    {"port": 1, "name": "AP", "disable": False},
                    {"port": 2, "name": "Unused", "disable": True},
                ],
            },
            {"mac": "11-22-33-44-55-66", "ports": [{"port": 1, "name": "other", "disable": False}]},
        ]
    }
    resource = SwitchesResource(http)

    ports = resource.get_ports(site_id="site-1", switch_mac="aa:bb:cc:dd:ee:ff")

    assert ports == [{"port": 1, "name": "AP", "disable": False}, {"port": 2, "name": "Unused", "disable": True}]
    method, url, kwargs = http.requests[0]
    assert method == "POST"
    assert "switches/ports/select" in url
    assert kwargs["json"]["selectAll"] is True
    assert kwargs["json"]["filters"]["switchMac"] == "AA-BB-CC-DD-EE-FF"


def test_get_ports_returns_empty_when_switch_not_found() -> None:
    http = DummyHttpClient()
    http._post_response = {"result": []}
    resource = SwitchesResource(http)

    ports = resource.get_ports(site_id="site-1", switch_mac="aa:bb:cc:dd:ee:ff")

    assert ports == []


def test_set_ports_name_sends_correct_body() -> None:
    http = DummyHttpClient()
    resource = SwitchesResource(http)

    resource.set_ports_name(
        site_id="site-1",
        switch_mac="aa:bb:cc:dd:ee:ff",
        port_names=[{"port": 1, "name": "uplink"}, {"port": 2, "name": "AP"}],
    )

    method, url, kwargs = http.requests[0]
    assert method == "PUT"
    assert "AA-BB-CC-DD-EE-FF" in url
    assert "multi-ports/name" in url
    assert kwargs["json"] == {"portNameList": [{"port": 1, "name": "uplink"}, {"port": 2, "name": "AP"}]}


def test_set_ports_status_enable_sends_disable_false() -> None:
    http = DummyHttpClient()
    resource = SwitchesResource(http)

    resource.set_ports_status(site_id="site-1", switch_mac="aa:bb:cc:dd:ee:ff", port_list=[3, 4], enabled=True)

    method, url, kwargs = http.requests[0]
    assert method == "PATCH"
    assert "multi-ports/config" in url
    assert kwargs["json"] == {"portList": [3, 4], "disable": False}


def test_set_ports_status_disable_sends_disable_true() -> None:
    http = DummyHttpClient()
    resource = SwitchesResource(http)

    resource.set_ports_status(site_id="site-1", switch_mac="aa:bb:cc:dd:ee:ff", port_list=[5], enabled=False)

    method, _, kwargs = http.requests[0]
    assert method == "PATCH"
    assert kwargs["json"] == {"portList": [5], "disable": True}
