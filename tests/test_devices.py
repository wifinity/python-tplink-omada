from __future__ import annotations

from omada_client.resources.devices import DevicesResource


class DummyClient:
    def __init__(self) -> None:
        self.calls = []

    def post(self, path: str, json=None):
        self.calls.append(("POST", path, json))
        if path.endswith("/forget"):
            return {"forgotten": True}
        if path.endswith("/start-adopt"):
            return {"adopting": True}
        if path.endswith("/multi-devices/devicekey-add"):
            return {"result": {"operateId": "op-1"}}
        return {"ok": True}

    def delete(self, path: str, json=None):
        self.calls.append(("DELETE", path, json))
        return {"ok": True}

    def get(self, path: str, params=None):
        self.calls.append(("GET", path, params))
        if "/aps/" in path:
            return {"deviceMac": "aa:bb:cc:dd:ee:ff", "name": "AP-1"}
        if path.endswith("/adopt-result"):
            return {
                "errorCode": 0,
                "msg": "Success.",
                "result": {
                    "deviceMac": "8C-86-DD-21-B4-2E",
                    "adoptErrorCode": -39005,
                    "adoptFailedType": -1,
                },
            }
        if path.endswith("/devices"):
            search_key = (params or {}).get("searchKey")
            if search_key:
                return {
                    "result": {
                        "data": [{"deviceMac": search_key, "name": "device-match", "status": 1, "detailStatus": 14}]
                    }
                }
            return {"result": {"data": [{"deviceMac": "00:11:22:33:44:55"}]}}
        return {"status": "online"}


def test_device_workflow_calls_expected_paths() -> None:
    client = DummyClient()
    resource = DevicesResource(client)

    resource.register(site_id="s1", device_data={"sn": "abc"})
    resource.remove(site_id="s1", device_ids=["d1"])
    resource.send_config(site_id="s1", device_id="d1", config={"k": "v"})
    status = resource.status(site_id="s1", device_id="d1")

    assert status == {"status": "online"}
    assert client.calls[0] == ("POST", "/openapi/v1/sites/s1/devices", {"sn": "abc"})
    assert client.calls[1] == ("DELETE", "/openapi/v1/sites/s1/devices", {"deviceIds": ["d1"]})
    assert client.calls[2] == ("POST", "/openapi/v1/sites/s1/devices/d1/config", {"k": "v"})
    assert client.calls[3] == ("GET", "/openapi/v1/sites/s1/devices/d1/status", None)


def test_device_canonical_methods_call_expected_paths() -> None:
    client = DummyClient()
    resource = DevicesResource(client)

    listed = resource.list(site_id="s1")
    by_mac = resource.get_by_mac(site_id="s1", mac="00:11:22:33:44:55")
    ap_by_mac = resource.get_by_mac(site_id="s1", mac="aa:bb:cc:dd:ee:ff", device_type="ap")
    created = resource.create(site_id="s1", device_data={"sn": "abc"})
    adopted = resource.start_adopt(site_id="s1", mac="aa:bb:cc:dd:ee:ff")
    adopt_check = resource.check_adopt(site_id="s1", mac="aa:bb:cc:dd:ee:ff")
    device_key_add = resource.add_by_device_key(
        site_id="s1",
        device_key="ZTP-DEVICE-KEY",
        name="AP-1",
        username="admin",
        password="pass",
    )
    deleted = resource.delete(site_id="s1", mac="aa:bb:cc:dd:ee:ff")

    assert listed == {"result": {"data": [{"deviceMac": "00:11:22:33:44:55"}]}}
    assert by_mac == {
        "deviceMac": "00-11-22-33-44-55",
        "name": "device-match",
        "status": 1,
        "detailStatus": 14,
        "statusMeaning": "Connected",
        "detailStatusMeaning": "Connected",
    }
    assert ap_by_mac == {"deviceMac": "aa:bb:cc:dd:ee:ff", "name": "AP-1"}
    assert created == {"ok": True}
    assert adopted == {"adopting": True}
    assert adopt_check == {
        "errorCode": 0,
        "msg": "Success.",
        "result": {
            "deviceMac": "8C-86-DD-21-B4-2E",
            "adoptErrorCode": -39005,
            "adoptFailedType": -1,
            "adoptErrorMeaning": "Failed to adopt this device because the device is not connected",
            "adoptFailedTypeMeaning": "No need print username or password",
        },
    }
    assert device_key_add == {"result": {"operateId": "op-1"}}
    assert deleted == {"forgotten": True}

    assert client.calls[0] == (
        "GET",
        "/openapi/v1/sites/s1/devices",
        {"page": 1, "pageSize": 1000},
    )
    assert client.calls[1] == (
        "GET",
        "/openapi/v1/sites/s1/devices",
        {"page": 1, "pageSize": 1000, "searchKey": "00-11-22-33-44-55"},
    )
    assert client.calls[2] == ("GET", "/openapi/v1/sites/s1/aps/AA-BB-CC-DD-EE-FF", None)
    assert client.calls[3] == ("POST", "/openapi/v1/sites/s1/devices", {"sn": "abc"})
    assert client.calls[4] == (
        "POST",
        "/openapi/v1/sites/s1/devices/AA-BB-CC-DD-EE-FF/start-adopt",
        {"username": "admin", "password": "admin"},
    )
    assert client.calls[5] == (
        "GET",
        "/openapi/v1/sites/s1/devices/AA-BB-CC-DD-EE-FF/adopt-result",
        None,
    )
    assert client.calls[6] == (
        "POST",
        "/openapi/v1/sites/s1/multi-devices/devicekey-add",
        {
            "devices": [
                {
                    "deviceKey": "ZTP-DEVICE-KEY",
                    "name": "AP-1",
                    "username": "admin",
                    "password": "pass",
                }
            ]
        },
    )
    assert client.calls[7] == ("POST", "/openapi/v1/sites/s1/devices/AA-BB-CC-DD-EE-FF/forget", None)


class OmadacPathDummyClient(DummyClient):
    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/omadac-1/")


def test_device_workflow_uses_api_path_rewrite() -> None:
    client = OmadacPathDummyClient()
    resource = DevicesResource(client)

    resource.register(site_id="s1", device_data={"sn": "abc"})
    resource.remove(site_id="s1", device_ids=["d1"])
    resource.send_config(site_id="s1", device_id="d1", config={"k": "v"})
    resource.status(site_id="s1", device_id="d1")

    assert client.calls[0] == ("POST", "/openapi/v1/omadac-1/sites/s1/devices", {"sn": "abc"})
    assert client.calls[1] == ("DELETE", "/openapi/v1/omadac-1/sites/s1/devices", {"deviceIds": ["d1"]})
    assert client.calls[2] == ("POST", "/openapi/v1/omadac-1/sites/s1/devices/d1/config", {"k": "v"})
    assert client.calls[3] == ("GET", "/openapi/v1/omadac-1/sites/s1/devices/d1/status", None)


def test_device_canonical_methods_use_api_path_rewrite() -> None:
    client = OmadacPathDummyClient()
    resource = DevicesResource(client)

    resource.list(site_id="s1", page=2, page_size=50)
    resource.get_by_mac(site_id="s1", mac="aa:bb:cc:dd:ee:ff", device_type="ap")
    resource.create(site_id="s1", device_data={"sn": "abc"})
    resource.start_adopt(site_id="s1", mac="aa:bb:cc:dd:ee:ff")
    resource.check_adopt(site_id="s1", mac="aa:bb:cc:dd:ee:ff")
    resource.add_by_device_key(site_id="s1", device_key="ZTP-DEVICE-KEY")
    resource.delete(site_id="s1", mac="aa:bb:cc:dd:ee:ff")

    assert client.calls[0] == ("GET", "/openapi/v1/omadac-1/sites/s1/devices", {"page": 2, "pageSize": 50})
    assert client.calls[1] == ("GET", "/openapi/v1/omadac-1/sites/s1/aps/AA-BB-CC-DD-EE-FF", None)
    assert client.calls[2] == ("POST", "/openapi/v1/omadac-1/sites/s1/devices", {"sn": "abc"})
    assert client.calls[3] == (
        "POST",
        "/openapi/v1/omadac-1/sites/s1/devices/AA-BB-CC-DD-EE-FF/start-adopt",
        {"username": "admin", "password": "admin"},
    )
    assert client.calls[4] == (
        "GET",
        "/openapi/v1/omadac-1/sites/s1/devices/AA-BB-CC-DD-EE-FF/adopt-result",
        None,
    )
    assert client.calls[5] == (
        "POST",
        "/openapi/v1/omadac-1/sites/s1/multi-devices/devicekey-add",
        {"devices": [{"deviceKey": "ZTP-DEVICE-KEY"}]},
    )
    assert client.calls[6] == ("POST", "/openapi/v1/omadac-1/sites/s1/devices/AA-BB-CC-DD-EE-FF/forget", None)


def test_get_by_mac_matches_device_mac_across_supported_input_formats() -> None:
    client = DummyClient()
    resource = DevicesResource(client)

    result = resource.get_by_mac(site_id="s1", mac="0011.2233.4455")

    assert result == {
        "deviceMac": "00-11-22-33-44-55",
        "name": "device-match",
        "status": 1,
        "detailStatus": 14,
        "statusMeaning": "Connected",
        "detailStatusMeaning": "Connected",
    }
    assert client.calls[0] == (
        "GET",
        "/openapi/v1/sites/s1/devices",
        {"page": 1, "pageSize": 1000, "searchKey": "00-11-22-33-44-55"},
    )


def test_mac_validation_raises_before_http_call_for_invalid_mac() -> None:
    client = DummyClient()
    resource = DevicesResource(client)

    try:
        resource.start_adopt(site_id="s1", mac="not-a-mac")
        assert False, "Expected ValueError for invalid MAC"
    except ValueError as exc:
        assert "Invalid MAC address" in str(exc)

    assert client.calls == []


def test_start_adopt_forwards_explicit_credentials() -> None:
    client = DummyClient()
    resource = DevicesResource(client)

    resource.start_adopt(
        site_id="s1",
        mac="aa:bb:cc:dd:ee:ff",
        username="admin",
        password="pass",
    )

    assert client.calls[0] == (
        "POST",
        "/openapi/v1/sites/s1/devices/AA-BB-CC-DD-EE-FF/start-adopt",
        {"username": "admin", "password": "pass"},
    )


def test_start_adopt_forwards_explicit_credentials_with_api_path_rewrite() -> None:
    client = OmadacPathDummyClient()
    resource = DevicesResource(client)

    resource.start_adopt(
        site_id="s1",
        mac="aa:bb:cc:dd:ee:ff",
        username="admin",
        password="pass",
    )

    assert client.calls[0] == (
        "POST",
        "/openapi/v1/omadac-1/sites/s1/devices/AA-BB-CC-DD-EE-FF/start-adopt",
        {"username": "admin", "password": "pass"},
    )


def test_check_adopt_populates_unknown_meaning_fallbacks() -> None:
    class UnknownAdoptCodeDummyClient(DummyClient):
        def get(self, path: str, params=None):
            if path.endswith("/adopt-result"):
                self.calls.append(("GET", path, params))
                return {
                    "errorCode": 0,
                    "msg": "Success.",
                    "result": {
                        "deviceMac": "8C-86-DD-21-B4-2E",
                        "adoptErrorCode": -99999,
                        "adoptFailedType": -12345,
                    },
                }
            return super().get(path, params=params)

    client = UnknownAdoptCodeDummyClient()
    resource = DevicesResource(client)

    response = resource.check_adopt(site_id="s1", mac="aa:bb:cc:dd:ee:ff")

    assert response["result"]["adoptErrorMeaning"] == "Unknown adoptErrorCode: -99999"
    assert response["result"]["adoptFailedTypeMeaning"] == "Unknown adoptFailedType: -12345"


def test_get_by_mac_populates_unknown_device_status_meaning_fallbacks() -> None:
    class UnknownDeviceStatusDummyClient(DummyClient):
        def get(self, path: str, params=None):
            if path.endswith("/devices"):
                self.calls.append(("GET", path, params))
                return {
                    "result": {
                        "data": [
                            {
                                "deviceMac": "00-11-22-33-44-55",
                                "name": "device-match",
                                "status": 99,
                                "detailStatus": 999,
                            }
                        ]
                    }
                }
            return super().get(path, params=params)

    client = UnknownDeviceStatusDummyClient()
    resource = DevicesResource(client)

    result = resource.get_by_mac(site_id="s1", mac="00:11:22:33:44:55")

    assert result["statusMeaning"] == "Unknown status: 99"
    assert result["detailStatusMeaning"] == "Unknown detailStatus: 999"


def test_check_adopt_invalid_mac_raises_before_http_call() -> None:
    client = DummyClient()
    resource = DevicesResource(client)

    try:
        resource.check_adopt(site_id="s1", mac="not-a-mac")
        assert False, "Expected ValueError for invalid MAC"
    except ValueError as exc:
        assert "Invalid MAC address" in str(exc)

    assert client.calls == []
