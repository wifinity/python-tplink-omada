from __future__ import annotations

from omada_client.exceptions import DeviceNotFoundError
from omada_client.resources.aps import APsResource

# Representative AP ethernet-port fixtures (shapes verified against a live controller).
# The capability read returns capability flags only (no live status/name/VLAN state).
AP_PORT_CAPABILITIES = [
    {
        "id": "ETH0",
        "lanPort": "ETH0",
        "supportVlan": True,
        "supportPoe": True,
        "supportVlanOption": True,
        "supportVlanTagged": True,
        "supportStatusEnable": True,
        "supportBandwidthControl": True,
    },
    {
        "id": "ETH1",
        "lanPort": "ETH1",
        "supportVlan": True,
        "supportPoe": False,
        "supportVlanOption": True,
        "supportVlanTagged": True,
        "supportStatusEnable": True,
        "supportBandwidthControl": True,
    },
]

# port-vlans lists only non-default VLAN associations (VLAN-1 native is implicit).
AP_PORT_VLANS = [
    {
        "localVlanId": 98,
        "localVlanNetworkId": "net-98",
        "name": "TPLAB - Open",
        "nativePorts": ["ETH0"],
        "tagPorts": [],
        "untagPorts": [],
    },
    {
        "localVlanId": 99,
        "localVlanNetworkId": "net-99",
        "name": "TPLAB - Onboarding",
        "nativePorts": [],
        "tagPorts": ["ETH0"],
        "untagPorts": [],
    },
]


class DummyDevicesResource:
    def __init__(self) -> None:
        self.calls = []

    def all(self, *, site_id: str, page: int = 1, page_size: int = 1000, **params):
        self.calls.append(("list", site_id, page, page_size, params))
        search_key = params.get("searchKey")
        if search_key is None and params.get("deviceType") == "ap":
            return {
                "result": {
                    "data": [
                        {
                            "mac": "AA-BB-CC-DD-EE-FF",
                            "name": "AP-1",
                            "sn": "AABB12345678",
                            "status": 1,
                            "detailStatus": 14,
                        }
                    ]
                }
            }
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
        if path.endswith("/port-vlans"):
            return {"result": {"totalRows": len(AP_PORT_VLANS), "data": list(AP_PORT_VLANS)}}
        return {"result": {"mac": "AA-BB-CC-DD-EE-FF", "name": "AP-Overview"}}

    def post(self, path: str, json=None):
        self.calls.append(("POST", path, json))
        if path.endswith("/aps/ports/capability"):
            return {"errorCode": 0, "result": list(AP_PORT_CAPABILITIES)}
        if path.endswith("/aps/ports/config"):
            return {"errorCode": 0, "msg": "Success.", "result": {"configResultList": []}}
        raise AssertionError(f"unexpected POST {path}")

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


def test_aps_resource_get_by_serial() -> None:
    client = DummyClient()
    resource = APsResource(client)

    by_serial = resource.get_by_serial(site_id="s1", serial="AABB12345678")

    assert by_serial == {
        "mac": "AA-BB-CC-DD-EE-FF",
        "name": "AP-1",
        "sn": "AABB12345678",
        "status": 1,
        "detailStatus": 14,
        "statusMeaning": "Connected",
        "detailStatusMeaning": "Connected",
    }
    assert client.devices.calls[-1] == ("list", "s1", 1, 1000, {"deviceType": "ap"})


def test_aps_resource_get_by_serial_not_found_raises_device_not_found() -> None:
    client = DummyClient()
    resource = APsResource(client)

    try:
        resource.get_by_serial(site_id="s1", serial="UNKNOWN-SERIAL")
        assert False, "Expected DeviceNotFoundError for missing AP serial"
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


def test_get_ports_posts_capability_and_returns_rows() -> None:
    client = DummyClient()
    resource = APsResource(client)

    ports = resource.get_ports(site_id="s1", mac="aa:bb:cc:dd:ee:ff")

    assert ports == AP_PORT_CAPABILITIES
    assert client.calls == [
        ("POST", "/openapi/v1/omadac-1/sites/s1/aps/ports/capability", {"apMacList": ["AA-BB-CC-DD-EE-FF"]})
    ]


def test_get_ports_returns_empty_when_no_result() -> None:
    class EmptyCapabilityClient(DummyClient):
        def post(self, path: str, json=None):
            self.calls.append(("POST", path, json))
            return {"errorCode": 0, "result": []}

    client = EmptyCapabilityClient()
    resource = APsResource(client)

    assert resource.get_ports(site_id="s1", mac="aa:bb:cc:dd:ee:ff") == []


def test_get_port_vlans_gets_with_page_params_and_returns_data() -> None:
    client = DummyClient()
    resource = APsResource(client)

    vlans = resource.get_port_vlans(site_id="s1", mac="aa:bb:cc:dd:ee:ff")

    assert vlans == AP_PORT_VLANS
    assert client.calls == [
        ("GET", "/openapi/v1/omadac-1/sites/s1/aps/AA-BB-CC-DD-EE-FF/port-vlans", {"page": 1, "pageSize": 1000})
    ]


def test_update_ports_posts_config_with_merged_body_verbatim() -> None:
    client = DummyClient()
    resource = APsResource(client)

    # Daisy-chain trunk (By-Network): VLAN-1-untagged management via omitted
    # localVlanNetworkId, service VLANs tagged, PoE-out on.
    settings = {
        "status": True,
        "poeOutEnable": True,
        "custom": False,
        "localVlanEnable": True,
        "taggedNetworkId": ["net-98", "net-99"],
        "untaggedNetworkId": [],
    }
    result = resource.update_ports(site_id="s1", mac="aa:bb:cc:dd:ee:ff", ports=["ETH0"], settings=settings)

    assert result == {"errorCode": 0, "msg": "Success.", "result": {"configResultList": []}}
    assert client.calls == [
        (
            "POST",
            "/openapi/v1/omadac-1/sites/s1/aps/ports/config",
            {"apMacList": ["AA-BB-CC-DD-EE-FF"], "lanPortList": ["ETH0"], **settings},
        )
    ]


def test_update_ports_passes_arbitrary_fields_through_unchanged() -> None:
    client = DummyClient()
    resource = APsResource(client)

    settings = {"name": "uplink", "status": False, "surprise": 42}
    resource.update_ports(site_id="s1", mac="AA-BB-CC-DD-EE-FF", ports=["ETH2", "ETH3"], settings=settings)

    _method, _url, body = client.calls[0]
    assert body == {"apMacList": ["AA-BB-CC-DD-EE-FF"], "lanPortList": ["ETH2", "ETH3"], **settings}


def test_ap_port_methods_reject_invalid_mac() -> None:
    client = DummyClient()
    resource = APsResource(client)

    for call in (
        lambda: resource.get_ports(site_id="s1", mac="bad-mac"),
        lambda: resource.get_port_vlans(site_id="s1", mac="bad-mac"),
        lambda: resource.update_ports(site_id="s1", mac="bad-mac", ports=["ETH0"], settings={"status": True}),
    ):
        try:
            call()
            assert False, "Expected ValueError for invalid MAC"
        except ValueError as exc:
            assert "Invalid MAC address" in str(exc)

    assert client.calls == []
