"""Unit tests for SiteWirelessResource.

Uses the DummyHttpClient capture pattern (see test_dhcp_snooping.py): stub the GET
response, call the method, assert on the captured (method, url, kwargs). The
read-modify-write merge is the key behaviour — setters must echo the untouched
blocks back so the controller's required-field validation passes.
"""

from omada_client.resources import SiteWirelessResource


class DummyHttpClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict]] = []
        self._get_response: dict = {}
        self._patch_response: dict = {"errorCode": 0, "msg": "Success."}

    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/OMADACID/")

    def get(self, url: str, **kwargs) -> dict:
        self.requests.append(("GET", url, kwargs))
        return self._get_response

    def patch(self, url: str, **kwargs) -> dict:
        self.requests.append(("PATCH", url, kwargs))
        return self._patch_response


def _mesh_response() -> dict:
    return {
        "errorCode": 0,
        "result": {
            "mesh": {
                "meshEnable": True,
                "autoFailoverEnable": True,
                "defGatewayEnable": True,
                "fullSector": True,
            }
        },
    }


def _beacon_response() -> dict:
    return {
        "errorCode": 0,
        "result": {
            "beaconControl": {
                "dtimPeriod2g": 1,
                "dtimPeriod5g": 1,
                "dtimPeriod6g": 1,
                "rtsThreshold2g": 2347,
                "rtsThreshold5g": 2347,
                "rtsThreshold6g": 2347,
            },
            "airtimeFairness": {"enable2g": False, "enable5g": False, "enable6g": False},
        },
    }


def test_get_mesh_returns_mesh_block() -> None:
    http = DummyHttpClient()
    http._get_response = _mesh_response()
    resource = SiteWirelessResource(http)

    assert resource.get_mesh(site_id="site-1") == {
        "meshEnable": True,
        "autoFailoverEnable": True,
        "defGatewayEnable": True,
        "fullSector": True,
    }
    method, url, _ = http.requests[0]
    assert method == "GET"
    assert "/openapi/v1/OMADACID/" in url
    assert url.endswith("/sites/site-1/mesh")


def test_get_mesh_defaults_empty_when_absent() -> None:
    http = DummyHttpClient()
    http._get_response = {"errorCode": 0, "result": {}}
    resource = SiteWirelessResource(http)

    assert resource.get_mesh(site_id="site-1") == {}


def test_set_mesh_disable_merges_and_patches_full_block() -> None:
    http = DummyHttpClient()
    http._get_response = _mesh_response()
    resource = SiteWirelessResource(http)

    resource.set_mesh(site_id="site-1", enabled=False)

    get_call, patch_call = http.requests
    assert get_call[0] == "GET"
    method, url, kwargs = patch_call
    assert method == "PATCH"
    assert url.endswith("/sites/site-1/mesh")
    assert kwargs["json"] == {
        "mesh": {
            "meshEnable": False,
            "autoFailoverEnable": True,
            "defGatewayEnable": True,
            "fullSector": True,
        }
    }


def test_set_mesh_enable_sets_true() -> None:
    http = DummyHttpClient()
    resp = _mesh_response()
    resp["result"]["mesh"]["meshEnable"] = False
    http._get_response = resp
    resource = SiteWirelessResource(http)

    resource.set_mesh(site_id="site-1", enabled=True)

    assert http.requests[1][2]["json"]["mesh"]["meshEnable"] is True


def test_get_airtime_fairness_returns_flags() -> None:
    http = DummyHttpClient()
    http._get_response = _beacon_response()
    resource = SiteWirelessResource(http)

    assert resource.get_airtime_fairness(site_id="site-1") == {
        "enable2g": False,
        "enable5g": False,
        "enable6g": False,
    }


def test_set_airtime_fairness_merges_flags_and_preserves_beacon_control() -> None:
    http = DummyHttpClient()
    http._get_response = _beacon_response()
    resource = SiteWirelessResource(http)

    resource.set_airtime_fairness(site_id="site-1", enable_2g=True, enable_5g=True, enable_6g=True)

    get_call, patch_call = http.requests
    assert get_call[0] == "GET"
    method, url, kwargs = patch_call
    assert method == "PATCH"
    assert url.endswith("/sites/site-1/beacon-control")
    body = kwargs["json"]
    assert body["airtimeFairness"] == {"enable2g": True, "enable5g": True, "enable6g": True}
    # beaconControl block echoed back unchanged so required fields stay satisfied
    assert body["beaconControl"] == _beacon_response()["result"]["beaconControl"]


def test_set_airtime_fairness_per_band_values() -> None:
    http = DummyHttpClient()
    http._get_response = _beacon_response()
    resource = SiteWirelessResource(http)

    resource.set_airtime_fairness(site_id="site-1", enable_2g=True, enable_5g=False, enable_6g=True)

    assert http.requests[1][2]["json"]["airtimeFairness"] == {
        "enable2g": True,
        "enable5g": False,
        "enable6g": True,
    }
