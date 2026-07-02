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
        self._delete_response: dict = {"errorCode": 0}

    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/OMADACID/").replace("/openapi/v2/", "/openapi/v2/OMADACID/")

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

    def delete(self, url: str, **kwargs) -> dict:
        self.requests.append(("DELETE", url, kwargs))
        return self._delete_response


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


def test_get_port_profiles_uses_v2_url() -> None:
    http = DummyHttpClient()
    http._get_response = {
        "result": {"data": [{"id": "profile-1", "name": "All"}, {"id": "profile-2", "name": "Disable"}]}
    }
    resource = SwitchesResource(http)

    profiles = resource.get_port_profiles(site_id="site-1")

    method, url, kwargs = http.requests[0]
    assert method == "GET"
    assert "/openapi/v2/" in url
    assert "lan-profiles" in url
    assert kwargs["params"] == {"page": 1, "pageSize": 1000}
    assert profiles == [{"id": "profile-1", "name": "All"}, {"id": "profile-2", "name": "Disable"}]


def test_set_port_profiles_puts_per_port_with_resolved_id() -> None:
    http = DummyHttpClient()
    http._get_response = {
        "result": {"data": [{"id": "profile-disable", "name": "Disable"}, {"id": "profile-all", "name": "All"}]}
    }
    resource = SwitchesResource(http)

    resource.set_port_profiles(
        site_id="site-1",
        switch_mac="aa:bb:cc:dd:ee:ff",
        port_list=[3, 5],
        profile_name="Disable",
    )

    put_requests = [(m, u, kw) for m, u, kw in http.requests if m == "PUT"]
    assert len(put_requests) == 2
    assert "ports/3/profile" in put_requests[0][1]
    assert "ports/5/profile" in put_requests[1][1]
    assert put_requests[0][2]["json"] == {"profileId": "profile-disable"}
    assert put_requests[1][2]["json"] == {"profileId": "profile-disable"}


def test_set_port_profiles_raises_for_unknown_profile() -> None:
    http = DummyHttpClient()
    http._get_response = {"result": {"data": [{"id": "profile-all", "name": "All"}]}}
    resource = SwitchesResource(http)

    try:
        resource.set_port_profiles(
            site_id="site-1",
            switch_mac="aa:bb:cc:dd:ee:ff",
            port_list=[1],
            profile_name="NonExistent",
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "NonExistent" in str(exc)


_PROFILE_BODY = {
    "name": "role-uplink",
    "bandWidthCtrlType": 0,
    "dot1x": 0,
    "lldpMedEnable": True,
    "loopbackDetectEnable": True,
    "poe": 2,
    "portIsolationEnable": False,
    "spanningTreeEnable": True,
}


def test_create_port_profile_posts_v2_and_returns_id() -> None:
    http = DummyHttpClient()
    http._post_response = {"result": {"id": "profile-new"}}
    resource = SwitchesResource(http)

    created = resource.create_port_profile(site_id="site-1", profile=_PROFILE_BODY)

    method, url, kwargs = http.requests[0]
    assert method == "POST"
    assert "/openapi/v2/OMADACID/" in url
    assert "sites/site-1/lan-profiles" in url
    assert kwargs["json"] == _PROFILE_BODY
    assert created == {"id": "profile-new"}


def test_update_port_profile_patches_v2_with_explicit_id() -> None:
    http = DummyHttpClient()
    resource = SwitchesResource(http)

    resource.update_port_profile(site_id="site-1", profile=_PROFILE_BODY, profile_id="profile-7")

    assert not any(m == "GET" for m, _u, _kw in http.requests)
    method, url, kwargs = http.requests[0]
    assert method == "PATCH"
    assert "/openapi/v2/OMADACID/" in url
    assert "sites/site-1/lan-profiles/profile-7" in url
    assert kwargs["json"] == _PROFILE_BODY


def test_update_port_profile_resolves_id_by_name() -> None:
    http = DummyHttpClient()
    http._get_response = {"result": {"data": [{"id": "profile-9", "name": "role-uplink"}]}}
    resource = SwitchesResource(http)

    resource.update_port_profile(site_id="site-1", profile=_PROFILE_BODY)

    get_requests = [(m, u, kw) for m, u, kw in http.requests if m == "GET"]
    patch_requests = [(m, u, kw) for m, u, kw in http.requests if m == "PATCH"]
    assert len(get_requests) == 1
    assert len(patch_requests) == 1
    assert "sites/site-1/lan-profiles/profile-9" in patch_requests[0][1]
    assert patch_requests[0][2]["json"] == _PROFILE_BODY


def test_update_port_profile_raises_for_unknown_name() -> None:
    http = DummyHttpClient()
    http._get_response = {"result": {"data": [{"id": "profile-other", "name": "role-other"}]}}
    resource = SwitchesResource(http)

    try:
        resource.update_port_profile(site_id="site-1", profile=_PROFILE_BODY)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "role-uplink" in str(exc)
    assert not any(m == "PATCH" for m, _u, _kw in http.requests)


def test_update_port_profile_raises_for_duplicate_name() -> None:
    http = DummyHttpClient()
    http._get_response = {
        "result": {"data": [{"id": "profile-a", "name": "role-uplink"}, {"id": "profile-b", "name": "role-uplink"}]}
    }
    resource = SwitchesResource(http)

    try:
        resource.update_port_profile(site_id="site-1", profile=_PROFILE_BODY)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Multiple" in str(exc)
    assert not any(m == "PATCH" for m, _u, _kw in http.requests)


def test_delete_port_profile_deletes_v2_by_id() -> None:
    http = DummyHttpClient()
    resource = SwitchesResource(http)

    resource.delete_port_profile(site_id="site-1", profile_id="profile-7")

    assert not any(m == "GET" for m, _u, _kw in http.requests)
    method, url, _kwargs = http.requests[0]
    assert method == "DELETE"
    assert "/openapi/v2/OMADACID/" in url
    assert "sites/site-1/lan-profiles/profile-7" in url


def test_delete_port_profile_resolves_id_by_name() -> None:
    http = DummyHttpClient()
    http._get_response = {"result": {"data": [{"id": "profile-9", "name": "role-uplink"}]}}
    resource = SwitchesResource(http)

    resource.delete_port_profile(site_id="site-1", name="role-uplink")

    delete_requests = [(m, u, kw) for m, u, kw in http.requests if m == "DELETE"]
    assert len(delete_requests) == 1
    assert "sites/site-1/lan-profiles/profile-9" in delete_requests[0][1]


def test_delete_port_profile_requires_exactly_one_selector() -> None:
    resource = SwitchesResource(DummyHttpClient())

    for kwargs in ({}, {"profile_id": "p", "name": "n"}):
        try:
            resource.delete_port_profile(site_id="site-1", **kwargs)
            assert False, "Expected ValueError"
        except ValueError as exc:
            assert "exactly one" in str(exc)


def test_upsert_port_profile_updates_on_name_hit() -> None:
    http = DummyHttpClient()
    http._get_response = {"result": {"data": [{"id": "profile-9", "name": "role-uplink"}]}}
    resource = SwitchesResource(http)

    result, created = resource.upsert_port_profile(site_id="site-1", profile=_PROFILE_BODY)

    assert created is False
    assert result == {"id": "profile-9", "name": "role-uplink"}
    get_requests = [r for r in http.requests if r[0] == "GET"]
    patch_requests = [r for r in http.requests if r[0] == "PATCH"]
    post_requests = [r for r in http.requests if r[0] == "POST"]
    # exactly one list resolve (upsert's get_port_profiles; update was given the id)
    assert len(get_requests) == 1
    assert len(patch_requests) == 1
    assert len(post_requests) == 0
    assert "sites/site-1/lan-profiles/profile-9" in patch_requests[0][1]


def test_upsert_port_profile_creates_on_name_miss() -> None:
    http = DummyHttpClient()
    http._get_response = {"result": {"data": [{"id": "profile-other", "name": "role-other"}]}}
    http._post_response = {"result": {"id": "profile-new"}}
    resource = SwitchesResource(http)

    result, created = resource.upsert_port_profile(site_id="site-1", profile=_PROFILE_BODY)

    assert created is True
    assert result == {"id": "profile-new"}
    patch_requests = [r for r in http.requests if r[0] == "PATCH"]
    post_requests = [r for r in http.requests if r[0] == "POST"]
    assert len(patch_requests) == 0
    assert len(post_requests) == 1
    assert post_requests[0][2]["json"] == _PROFILE_BODY


def test_upsert_port_profile_requires_name() -> None:
    resource = SwitchesResource(DummyHttpClient())

    try:
        resource.upsert_port_profile(site_id="site-1", profile={"poe": 2})
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "name" in str(exc)


def test_update_switch_port_patches_correct_url_with_normalized_mac() -> None:
    http = DummyHttpClient()
    resource = SwitchesResource(http)

    settings = {"name": "AP-uplink", "profileId": "profile-1", "profileOverrideEnable": False}
    resource.update_switch_port(
        site_id="site-1",
        switch_mac="aa:bb:cc:dd:ee:ff",
        port=5,
        settings=settings,
    )

    method, url, kwargs = http.requests[0]
    assert method == "PATCH"
    assert "/openapi/v1/OMADACID/" in url
    assert "switches/AA-BB-CC-DD-EE-FF/ports/5" in url
    assert kwargs["json"] == settings


def test_update_switch_port_round_trips_vlan_body_unchanged() -> None:
    http = DummyHttpClient()
    resource = SwitchesResource(http)

    settings = {
        "nativeNetworkId": "net-default",
        "nativeBridgeVlan": 1,
        "tagNetworkIds": ["net-10", "net-20"],
        "untagNetworkIds": ["net-30"],
        "networkTagsSetting": 2,
    }
    resource.update_switch_port(site_id="site-1", switch_mac="AA-BB-CC-DD-EE-FF", port=3, settings=settings)

    method, url, kwargs = http.requests[0]
    assert method == "PATCH"
    assert "switches/AA-BB-CC-DD-EE-FF/ports/3" in url
    assert kwargs["json"] == settings


def test_update_switch_port_round_trips_dhcp_snoop_trust() -> None:
    http = DummyHttpClient()
    resource = SwitchesResource(http)

    settings = {"dhcpSnoopEnable": True}
    resource.update_switch_port(site_id="site-1", switch_mac="AA-BB-CC-DD-EE-FF", port=7, settings=settings)

    _method, _url, kwargs = http.requests[0]
    assert kwargs["json"] == settings


def test_update_switch_port_round_trips_profile_attach_and_override() -> None:
    http = DummyHttpClient()
    resource = SwitchesResource(http)

    attach = {"profileId": "profile-all", "profileOverrideEnable": False}
    resource.update_switch_port(site_id="site-1", switch_mac="AA-BB-CC-DD-EE-FF", port=1, settings=attach)

    override = {"profileOverrideEnable": True, "poe": 2, "dot1x": 2, "stormCtrl": {"broadcastEnable": True}}
    resource.update_switch_port(site_id="site-1", switch_mac="AA-BB-CC-DD-EE-FF", port=2, settings=override)

    assert http.requests[0][2]["json"] == attach
    assert http.requests[1][2]["json"] == override


def test_update_switch_port_passes_arbitrary_fields_through_unchanged() -> None:
    # `disable` is just another OswPortSettingVO field passed through verbatim;
    # admin enable/disable is managed via set_port_profiles (Decision 30), not here.
    http = DummyHttpClient()
    resource = SwitchesResource(http)

    settings = {"disable": True, "name": "spare", "profileOverrideEnable": True}
    resource.update_switch_port(site_id="site-1", switch_mac="AA-BB-CC-DD-EE-FF", port=9, settings=settings)

    _method, _url, kwargs = http.requests[0]
    assert kwargs["json"] == settings


def test_update_switch_port_rejects_invalid_mac() -> None:
    http = DummyHttpClient()
    resource = SwitchesResource(http)

    try:
        resource.update_switch_port(site_id="site-1", switch_mac="bad-mac", port=1, settings={"name": "x"})
        assert False, "Expected ValueError for invalid MAC"
    except ValueError as exc:
        assert "Invalid MAC address" in str(exc)

    assert http.requests == []
