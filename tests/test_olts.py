from __future__ import annotations

from omada_client.resources.olts import OLTsResource


class DummyClient:
    def __init__(self) -> None:
        self.calls = []

    def get(self, path: str, params=None):
        self.calls.append(("GET", path, params))

        # List ONUs response shape similar to other list endpoints
        if path.endswith("/pon/onu-management/informations/list"):
            return {
                "result": {
                    "data": [
                        {
                            "key": "1-1-1_0",
                            "mac": "F0-09-0D-E4-09-83",
                            "receivedOpticalPower": -7.00,
                            "transmittedOpticalPower": 1.71,
                        }
                    ]
                }
            }

        # Detail response stub
        if path.endswith("/pon/onu-management/informations/detail/get"):
            return {
                "result": {
                    "onuOpticalLinkInformation": {
                        "receivedOpticalPower": -7.06,
                        "transmittedOpticalPower": 1.71,
                        "biasCurrent": 20.1,
                        "workingVoltage": 3240,
                        "workingTemperature": 57.43,
                    }
                }
            }

        return {"ok": True}


class OmadacPathDummyClient(DummyClient):
    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/omadac-1/")


def test_list_onus_calls_expected_path_and_params() -> None:
    client = DummyClient()
    resource = OLTsResource(client)

    payload = resource.list_onus(site_id="s1", olt_mac="9c:53:22:71:a3:54", pon_port="GPON 1/1/1")

    assert "result" in payload
    assert client.calls[0] == (
        "GET",
        "/openapi/v1/sites/s1/olts/9C-53-22-71-A3-54/pon/onu-management/informations/list",
        {"ponPort": "GPON 1/1/1"},
    )


def test_get_onu_detail_calls_expected_path_and_key_param() -> None:
    client = DummyClient()
    resource = OLTsResource(client)

    payload = resource.get_onu_detail(site_id="s1", olt_mac="9C-53-22-71-A3-54", onu_key="1-1-1_0")

    assert payload["result"]["onuOpticalLinkInformation"]["receivedOpticalPower"] == -7.06
    assert client.calls[0] == (
        "GET",
        "/openapi/v1/sites/s1/olts/9C-53-22-71-A3-54/pon/onu-management/informations/detail/get",
        {"key": "1-1-1_0"},
    )


def test_get_onu_detail_by_mac_performs_list_then_detail() -> None:
    client = DummyClient()
    resource = OLTsResource(client)

    payload = resource.get_onu_detail_by_mac(
        site_id="s1",
        olt_mac="9c:53:22:71:a3:54",
        pon_port="GPON 1/1/1",
        onu_mac="f0:09:0d:e4:09:83",
    )

    assert "onuOpticalLinkInformation" in payload["result"]
    assert client.calls[0] == (
        "GET",
        "/openapi/v1/sites/s1/olts/9C-53-22-71-A3-54/pon/onu-management/informations/list",
        {"ponPort": "GPON 1/1/1"},
    )
    assert client.calls[1] == (
        "GET",
        "/openapi/v1/sites/s1/olts/9C-53-22-71-A3-54/pon/onu-management/informations/detail/get",
        {"key": "1-1-1_0"},
    )


def test_api_path_rewrite_is_used() -> None:
    client = OmadacPathDummyClient()
    resource = OLTsResource(client)

    resource.list_onus(site_id="s1", olt_mac="9c:53:22:71:a3:54", pon_port="GPON 1/1/1")

    assert client.calls[0] == (
        "GET",
        "/openapi/v1/omadac-1/sites/s1/olts/9C-53-22-71-A3-54/pon/onu-management/informations/list",
        {"ponPort": "GPON 1/1/1"},
    )


def test_resolve_onu_key_raises_when_not_found() -> None:
    client = DummyClient()
    resource = OLTsResource(client)

    try:
        resource.resolve_onu_key(
            site_id="s1",
            olt_mac="9c:53:22:71:a3:54",
            pon_port="GPON 1/1/1",
            onu_mac="00:11:22:33:44:55",
        )
        assert False, "Expected ValueError when ONU MAC not found"
    except ValueError as exc:
        assert "not found" in str(exc).lower()
