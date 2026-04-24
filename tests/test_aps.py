from __future__ import annotations

from omada_client.exceptions import DeviceNotFoundError
from omada_client.resources.aps import APsResource


class DummyDevicesResource:
    def __init__(self) -> None:
        self.calls = []

    def list(self, *, site_id: str, page: int = 1, page_size: int = 1000, **params):
        self.calls.append(("list", site_id, page, page_size, params))
        search_key = params.get("searchKey")
        if search_key == "AA-BB-CC-DD-EE-FF":
            return {"result": {"data": [{"mac": search_key, "name": "AP-1", "status": 1, "detailStatus": 14}]}}
        if search_key == "AP-1":
            return {"result": {"data": [{"mac": "AA-BB-CC-DD-EE-FF", "name": "AP-1", "status": 1, "detailStatus": 14}]}}
        if search_key == "UNKNOWN-AP":
            return {
                "result": {
                    "data": [{"mac": "AA-BB-CC-DD-EE-99", "name": "UNKNOWN-AP", "status": 99, "detailStatus": 999}]
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

    def get_by_mac(self, *, site_id: str, mac: str, device_type=None):
        self.calls.append(("get_by_mac", site_id, mac, device_type))
        return {"deviceMac": mac}

    def add_by_device_key(self, *, site_id: str, device_key: str):
        self.calls.append(("add_by_device_key", site_id, device_key))
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


class DummyClient:
    def __init__(self) -> None:
        self.devices = DummyDevicesResource()
        self.wlan_groups = DummyWLANGroupsResource()
        self.calls = []

    def get(self, path: str, params=None):
        self.calls.append(("GET", path, params))
        if path.endswith("/wired-uplink"):
            return {"result": {"wiredUplink": {"portType": 0, "linkStatus": 1, "linkSpeed": 3, "duplex": 2}}}
        return {"result": {"mac": "AA-BB-CC-DD-EE-FF", "name": "AP-Overview"}}

    def patch(self, path: str, json=None):
        self.calls.append(("PATCH", path, json))
        return {"result": {"success": True}}

    def api_path(self, path: str) -> str:
        return f"/openapi/v1/omadac-1/{path[len('/openapi/v1/'):]}"


class DummyWLANGroupsResource:
    def __init__(self) -> None:
        self.calls = []
        self.by_id = {
            "w1": {"wlanId": "w1", "name": "Corp"},
            "w2": {"wlanId": "w2", "name": "Guest"},
        }
        self.by_name = {
            "Corp": {"wlanId": "w1", "name": "Corp"},
            "Guest": {"wlanId": "w2", "name": "Guest"},
        }

    def get(self, *, site_id: str, id: str | None = None, name: str | None = None):
        if (id is None) == (name is None):
            raise ValueError("Provide exactly one of 'id' or 'name'")
        if id is not None:
            self.calls.append(("id", site_id, id))
            if id in self.by_id:
                return self.by_id[id]
            raise ValueError(f"WLAN group with id '{id}' was not found")
        self.calls.append(("name", site_id, name))
        if name in self.by_name:
            return self.by_name[name]
        raise ValueError(f"WLAN group with name '{name}' was not found")


def test_aps_resource_delegates_to_devices_with_ap_options() -> None:
    client = DummyClient()
    resource = APsResource(client)

    listed = resource.all(site_id="s1", page=2, page_size=50, searchKey="ap")
    by_mac = resource.get_by_mac(site_id="s1", mac="aa:bb:cc:dd:ee:ff")
    by_name = resource.get_by_name(site_id="s1", name="AP-1")
    overview = resource.get_overview_by_mac(site_id="s1", mac="aa:bb:cc:dd:ee:ff")
    wired_uplink = resource.get_wired_uplink_by_mac(site_id="s1", mac="aa:bb:cc:dd:ee:ff")
    created = resource.create(site_id="s1", device_key="ZTP-DEVICE-KEY")
    started_adopt = resource.start_adopt(
        site_id="s1",
        mac="aa:bb:cc:dd:ee:ff",
        username="admin",
        password="secret",
    )
    checked_adopt = resource.check_adopt(site_id="s1", mac="aa:bb:cc:dd:ee:ff")
    deleted = resource.delete(site_id="s1", mac="aa:bb:cc:dd:ee:ff")
    updated = resource.update(
        site_id="s1",
        mac="aa:bb:cc:dd:ee:ff",
        data={"name": "hostname"},
    )
    switched_wlan_group = resource.set_wlan_group_by_mac(
        site_id="s1",
        mac="aa:bb:cc:dd:ee:ff",
        wlan_group="Corp",
    )

    assert listed == {"items": []}
    assert by_mac == {
        "mac": "AA-BB-CC-DD-EE-FF",
        "name": "AP-1",
        "status": 1,
        "detailStatus": 14,
        "statusMeaning": "Connected",
        "detailStatusMeaning": "Connected",
    }
    assert by_name == {
        "mac": "AA-BB-CC-DD-EE-FF",
        "name": "AP-1",
        "status": 1,
        "detailStatus": 14,
        "statusMeaning": "Connected",
        "detailStatusMeaning": "Connected",
    }
    assert overview == {"result": {"mac": "AA-BB-CC-DD-EE-FF", "name": "AP-Overview"}}
    assert wired_uplink == {
        "result": {
            "wiredUplink": {
                "portType": 0,
                "portTypeMeaning": "ETH",
                "linkStatus": 1,
                "linkStatusMeaning": "Up",
                "linkSpeed": 3,
                "linkSpeedMeaning": "1000M",
                "duplex": 2,
                "duplexMeaning": "Full",
            }
        }
    }
    assert created == {"ok": True}
    assert started_adopt == {"started": True}
    assert checked_adopt == {"result": {"adoptErrorCode": 0, "adoptErrorMeaning": "Adopt Device Success"}}
    assert deleted == {"forgotten": True}
    assert updated == {"result": {"success": True}}
    assert switched_wlan_group == {"result": {"success": True}}
    assert client.devices.calls[0] == ("list", "s1", 2, 50, {"deviceType": "ap", "searchKey": "ap"})
    assert client.devices.calls[1] == ("list", "s1", 1, 1000, {"searchKey": "AA-BB-CC-DD-EE-FF", "deviceType": "ap"})
    assert client.devices.calls[2] == ("list", "s1", 1, 1000, {"searchKey": "AP-1", "deviceType": "ap"})
    assert client.devices.calls[3] == ("add_by_device_key", "s1", "ZTP-DEVICE-KEY")
    assert client.devices.calls[4] == ("start_adopt", "s1", "aa:bb:cc:dd:ee:ff", "admin", "secret")
    assert client.devices.calls[5] == ("check_adopt", "s1", "aa:bb:cc:dd:ee:ff")
    assert client.devices.calls[6] == ("delete", "s1", "AA-BB-CC-DD-EE-FF")
    assert client.calls[0] == ("GET", "/openapi/v1/omadac-1/sites/s1/aps/AA-BB-CC-DD-EE-FF", None)
    assert client.calls[1] == (
        "GET",
        "/openapi/v1/omadac-1/sites/s1/aps/AA-BB-CC-DD-EE-FF/wired-uplink",
        None,
    )
    assert client.calls[2] == (
        "PATCH",
        "/openapi/v1/omadac-1/sites/s1/aps/AA-BB-CC-DD-EE-FF/general-config",
        {"name": "hostname"},
    )
    assert client.calls[3] == (
        "PATCH",
        "/openapi/v1/omadac-1/sites/s1/aps/AA-BB-CC-DD-EE-FF/wlan-group",
        {"wlanGroupId": "w1"},
    )
    assert client.wlan_groups.calls == [("id", "s1", "Corp"), ("name", "s1", "Corp")]


def test_aps_resource_rejects_invalid_mac() -> None:
    client = DummyClient()
    resource = APsResource(client)

    try:
        resource.get_by_mac(site_id="s1", mac="bad-mac")
        assert False, "Expected ValueError for invalid MAC"
    except ValueError as exc:
        assert "Invalid MAC address" in str(exc)

    try:
        resource.update(site_id="s1", mac="bad-mac", data={"name": "hostname"})
        assert False, "Expected ValueError for invalid MAC"
    except ValueError as exc:
        assert "Invalid MAC address" in str(exc)

    try:
        resource.get_wired_uplink_by_mac(site_id="s1", mac="bad-mac")
        assert False, "Expected ValueError for invalid MAC"
    except ValueError as exc:
        assert "Invalid MAC address" in str(exc)

    assert client.devices.calls == []


def test_aps_resource_get_by_name_not_found_and_duplicate() -> None:
    client = DummyClient()
    resource = APsResource(client)

    try:
        resource.get_by_name(site_id="s1", name="missing")
        assert False, "Expected ValueError for missing AP name"
    except ValueError as exc:
        assert "not found" in str(exc)

    try:
        resource.get_by_name(site_id="s1", name="DUPLICATE")
        assert False, "Expected ValueError for duplicate AP names"
    except ValueError as exc:
        assert "Multiple APs named 'DUPLICATE'" in str(exc)


def test_aps_resource_get_by_mac_not_found_raises_device_not_found() -> None:
    client = DummyClient()
    resource = APsResource(client)

    try:
        resource.get_by_mac(site_id="s1", mac="aa:bb:cc:dd:ee:00")
        assert False, "Expected DeviceNotFoundError for missing AP MAC"
    except DeviceNotFoundError as exc:
        assert "not found" in str(exc)


def test_aps_resource_applies_unknown_status_meaning_fallbacks() -> None:
    client = DummyClient()
    resource = APsResource(client)

    by_name = resource.get_by_name(site_id="s1", name="UNKNOWN-AP")

    assert by_name["statusMeaning"] == "Unknown status: 99"
    assert by_name["detailStatusMeaning"] == "Unknown detailStatus: 999"


def test_aps_resource_applies_unknown_wired_uplink_meaning_fallbacks() -> None:
    class UnknownWiredUplinkClient(DummyClient):
        def get(self, path: str, params=None):
            self.calls.append(("GET", path, params))
            if path.endswith("/wired-uplink"):
                return {
                    "result": {
                        "wiredUplink": {
                            "portType": 99,
                            "linkStatus": 99,
                            "linkSpeed": 99,
                            "duplex": 99,
                        }
                    }
                }
            return {"result": {"mac": "AA-BB-CC-DD-EE-FF", "name": "AP-Overview"}}

    client = UnknownWiredUplinkClient()
    resource = APsResource(client)
    wired_uplink = resource.get_wired_uplink_by_mac(site_id="s1", mac="aa:bb:cc:dd:ee:ff")

    uplink = wired_uplink["result"]["wiredUplink"]
    assert uplink["portTypeMeaning"] == "Unknown portType: 99"
    assert uplink["linkStatusMeaning"] == "Unknown linkStatus: 99"
    assert uplink["linkSpeedMeaning"] == "Unknown linkSpeed: 99"
    assert uplink["duplexMeaning"] == "Unknown duplex: 99"


def test_get_overview_by_mac_enriches_wlan_group_name() -> None:
    class OverviewWithWlanClient(DummyClient):
        def get(self, path: str, params=None):
            self.calls.append(("GET", path, params))
            return {
                "result": {
                    "mac": "AA-BB-CC-DD-EE-FF",
                    "name": "AP-Overview",
                    "wlanId": "w1",
                }
            }

    client = OverviewWithWlanClient()
    resource = APsResource(client)

    overview = resource.get_overview_by_mac(site_id="s1", mac="aa:bb:cc:dd:ee:ff")

    assert overview["result"]["wlanId"] == "w1"
    assert overview["result"]["wlanGroupName"] == "Corp"
    assert client.wlan_groups.calls == [("id", "s1", "w1")]


def test_get_overview_by_mac_ignores_wlan_group_lookup_failures() -> None:
    class OverviewWithMissingWlanClient(DummyClient):
        def get(self, path: str, params=None):
            self.calls.append(("GET", path, params))
            return {
                "result": {
                    "mac": "AA-BB-CC-DD-EE-FF",
                    "name": "AP-Overview",
                    "wlanId": "missing",
                }
            }

    client = OverviewWithMissingWlanClient()
    resource = APsResource(client)

    overview = resource.get_overview_by_mac(site_id="s1", mac="aa:bb:cc:dd:ee:ff")

    assert overview["result"]["wlanId"] == "missing"
    assert "wlanGroupName" not in overview["result"]
    assert client.wlan_groups.calls == [("id", "s1", "missing")]


def test_get_overview_by_mac_supports_legacy_wlan_group_id_key() -> None:
    class OverviewWithLegacyWlanKeyClient(DummyClient):
        def get(self, path: str, params=None):
            self.calls.append(("GET", path, params))
            return {
                "result": {
                    "mac": "AA-BB-CC-DD-EE-FF",
                    "name": "AP-Overview",
                    "wlan group id": "w2",
                }
            }

    client = OverviewWithLegacyWlanKeyClient()
    resource = APsResource(client)

    overview = resource.get_overview_by_mac(site_id="s1", mac="aa:bb:cc:dd:ee:ff")

    assert overview["result"]["wlan group id"] == "w2"
    assert overview["result"]["wlanGroupName"] == "Guest"
    assert client.wlan_groups.calls == [("id", "s1", "w2")]


def test_set_wlan_group_by_mac_accepts_group_id() -> None:
    client = DummyClient()
    resource = APsResource(client)

    result = resource.set_wlan_group_by_mac(
        site_id="s1",
        mac="aa:bb:cc:dd:ee:ff",
        wlan_group="w2",
    )

    assert result == {"result": {"success": True}}
    assert client.calls == [
        (
            "PATCH",
            "/openapi/v1/omadac-1/sites/s1/aps/AA-BB-CC-DD-EE-FF/wlan-group",
            {"wlanGroupId": "w2"},
        )
    ]
    assert client.wlan_groups.calls == [("id", "s1", "w2")]


def test_set_wlan_group_by_mac_requires_non_empty_group() -> None:
    client = DummyClient()
    resource = APsResource(client)

    try:
        resource.set_wlan_group_by_mac(site_id="s1", mac="aa:bb:cc:dd:ee:ff", wlan_group="")
        assert False, "Expected ValueError for empty wlan_group"
    except ValueError as exc:
        assert "wlan_group must be a non-empty string" in str(exc)
