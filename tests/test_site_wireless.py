"""Unit tests for SiteWirelessResource.

Uses the DummyHttpClient capture pattern (see test_dhcp_snooping.py): stub the GET
response, call the method, assert on the captured (method, url, kwargs). The
read-modify-write merge is the key behaviour — setters must echo the untouched
blocks back so the controller's required-field validation passes.
"""

import pytest

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

    def put(self, url: str, **kwargs) -> dict:
        self.requests.append(("PUT", url, kwargs))
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


def _rrm_response() -> dict:
    return {"errorCode": 0, "result": {"mode": 0, "resource": 0, "timeRangeEnable": False}}


def _rf_planning_response() -> dict:
    return {
        "errorCode": 0,
        "result": {
            "mode": 1,
            "channelDeployEnable": True,
            "bandDeployEnable": True,
            "channelWidthDeployEnable": True,
            "powerAdjustEnable": True,
            "excludeAps": [],
            "occurrence": {"hour": 0, "minute": 0, "timingType": 1},
            "scheduleEnable": False,
            "resource": 0,
            "advancedSetting": {
                "exclude5gChEn": False,
                "exclude5gCh": [],
                "powerMode": 0,
                "powerThreshold": {"mode": 0},
                "widthSelectEn": False,
            },
        },
    }


def test_get_adaptive_optimization_returns_result() -> None:
    http = DummyHttpClient()
    http._get_response = _rrm_response()

    result = SiteWirelessResource(http).get_adaptive_optimization(site_id="site-1")

    assert result == {"mode": 0, "resource": 0, "timeRangeEnable": False}
    assert http.requests[0][1].endswith("/sites/site-1/rrm/config")


@pytest.mark.parametrize(("enabled", "mode"), [(True, 1), (False, 0)])
def test_set_adaptive_optimization_merges_mode_and_puts(enabled: bool, mode: int) -> None:
    http = DummyHttpClient()
    http._get_response = {"errorCode": 0, "result": {"mode": 1 - mode, "resource": 0, "timeRangeEnable": False}}

    SiteWirelessResource(http).set_adaptive_optimization(site_id="site-1", enabled=enabled)

    method, url, kwargs = http.requests[1]
    assert method == "PUT"
    assert url.endswith("/sites/site-1/rrm/config")
    assert kwargs["json"] == {"mode": mode, "resource": 0, "timeRangeEnable": False}


def test_set_adaptive_optimization_rejects_non_bool() -> None:
    with pytest.raises(ValueError, match="bool"):
        SiteWirelessResource(DummyHttpClient()).set_adaptive_optimization(site_id="site-1", enabled=1)  # type: ignore[arg-type]


def test_get_optimization_config_reads_rf_planning() -> None:
    http = DummyHttpClient()
    http._get_response = _rf_planning_response()

    result = SiteWirelessResource(http).get_optimization_config(site_id="site-1")

    assert result["mode"] == 1
    assert http.requests[0][1].endswith("/sites/site-1/rfPlanning")


def test_custom_setting_from_config_keeps_toggles_and_advanced_only() -> None:
    config = _rf_planning_response()["result"]

    custom = SiteWirelessResource.custom_setting_from_config(config)

    assert custom == {
        "channelDeployEnable": True,
        "bandDeployEnable": True,
        "channelWidthDeployEnable": True,
        "powerAdjustEnable": True,
        "advancedSetting": config["advancedSetting"],
    }


def test_set_optimization_config_custom_puts_mode_and_custom_setting() -> None:
    http = DummyHttpClient()
    custom = {
        "channelDeployEnable": True,
        "bandDeployEnable": True,
        "channelWidthDeployEnable": True,
        "powerAdjustEnable": True,
        "advancedSetting": {
            "widthSelectEn": True,
            "widthRange": {"minWidth5g": 20, "maxWidth5g": 40, "minWidth6g": 20, "maxWidth6g": 80},
            "powerMode": 0,
            "powerThreshold": {"mode": 0},
            "exclude5gChEn": False,
        },
    }

    SiteWirelessResource(http).set_optimization_config(site_id="site-1", mode=1, custom_setting=custom)

    method, url, kwargs = http.requests[0]
    assert method == "PUT"
    assert url.endswith("/sites/site-1/rfPlanning/config")
    assert kwargs["json"] == {"mode": 1, "customSetting": custom}


def test_set_optimization_config_default_sends_mode_only() -> None:
    http = DummyHttpClient()

    SiteWirelessResource(http).set_optimization_config(site_id="site-1", mode=0)

    assert http.requests[0][2]["json"] == {"mode": 0}


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"mode": 2}, "mode must be one of"),
        ({"mode": True}, "mode must be one of"),
        ({"mode": 1}, "non-empty dict"),
        ({"mode": 1, "custom_setting": {}}, "non-empty dict"),
        ({"mode": 0, "custom_setting": {"powerAdjustEnable": True}}, "only valid with mode=1"),
        (
            {"mode": 1, "custom_setting": {"advancedSetting": {"widthRange": {"minWidth5g": 20, "maxWidth5g": 320}}}},
            "5g channel width range",
        ),
        (
            {"mode": 1, "custom_setting": {"advancedSetting": {"widthRange": {"minWidth6g": 80, "maxWidth6g": 20}}}},
            "minimum 80 exceeds maximum 20",
        ),
    ],
)
def test_set_optimization_config_rejects_invalid_input_before_request(kwargs: dict, match: str) -> None:
    http = DummyHttpClient()

    with pytest.raises(ValueError, match=match):
        SiteWirelessResource(http).set_optimization_config(site_id="site-1", **kwargs)

    assert http.requests == []
