"""Unit tests for SwitchDot1xResource.

Mirrors the DummyHttpClient capture pattern in test_dhcp_snooping.py: set the
canned response, call the method, assert on the captured (method, url, kwargs)
tuple. Switch 802.1X is a single per-site resource (``/sites/{siteId}/dot1x``);
``get`` unwraps ``result`` and ``update`` passes the body through unchanged.
"""

from omada_client.resources import SwitchDot1xResource


class DummyHttpClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict]] = []
        self._get_response: dict = {}
        self._patch_response: dict = {"errorCode": 0}

    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/OMADACID/").replace("/openapi/v2/", "/openapi/v2/OMADACID/")

    def get(self, url: str, **kwargs) -> dict:
        self.requests.append(("GET", url, kwargs))
        return self._get_response

    def patch(self, url: str, **kwargs) -> dict:
        self.requests.append(("PATCH", url, kwargs))
        return self._patch_response


def test_get_returns_unwrapped_result() -> None:
    http = DummyHttpClient()
    http._get_response = {
        "errorCode": 0,
        "result": {"enable": True, "radiusProfileId": "r1", "nasId": "fsNas1", "authMode": 1},
    }
    resource = SwitchDot1xResource(http)

    setting = resource.get(site_id="site-1")

    assert setting == {"enable": True, "radiusProfileId": "r1", "nasId": "fsNas1", "authMode": 1}
    method, url, _ = http.requests[0]
    assert method == "GET"
    assert "/openapi/v1/OMADACID/" in url
    assert url.endswith("/sites/site-1/dot1x")


def test_get_defaults_empty_when_no_result() -> None:
    http = DummyHttpClient()
    http._get_response = {"errorCode": 0}
    resource = SwitchDot1xResource(http)

    assert resource.get(site_id="site-1") == {}


def test_candidates_returns_unwrapped_list() -> None:
    http = DummyHttpClient()
    http._get_response = {
        "errorCode": 0,
        "result": [
            {
                "mac": "AA-BB-CC-DD-EE-FF",
                "ports": [
                    {"port": 5, "dot1xEnable": False, "mabEnable": True, "authType": 2},
                    {"port": 6, "dot1xEnable": False, "mabEnable": False, "authType": 0},
                ],
            }
        ],
    }
    resource = SwitchDot1xResource(http)

    candidates = resource.candidates(site_id="site-1")

    assert candidates[0]["mac"] == "AA-BB-CC-DD-EE-FF"
    assert candidates[0]["ports"][0] == {"port": 5, "dot1xEnable": False, "mabEnable": True, "authType": 2}
    method, url, _ = http.requests[0]
    assert method == "GET"
    assert "/openapi/v1/OMADACID/" in url
    assert url.endswith("/sites/site-1/dot1x/candidates")


def test_candidates_unwraps_paginated_data() -> None:
    http = DummyHttpClient()
    http._get_response = {"errorCode": 0, "result": {"data": [{"mac": "AA-BB-CC-DD-EE-FF", "ports": []}]}}
    resource = SwitchDot1xResource(http)

    assert resource.candidates(site_id="site-1") == [{"mac": "AA-BB-CC-DD-EE-FF", "ports": []}]


def test_candidates_defaults_empty_when_no_result() -> None:
    http = DummyHttpClient()
    http._get_response = {"errorCode": 0}
    resource = SwitchDot1xResource(http)

    assert resource.candidates(site_id="site-1") == []


def test_update_patches_body_at_site_dot1x() -> None:
    http = DummyHttpClient()
    resource = SwitchDot1xResource(http)

    settings = {
        "enable": True,
        "authMode": 1,
        "authType": 0,
        "mab": False,
        "macFormat": 0,
        "radiusProfileId": "r1",
        "vlanAssign": False,
        "nasId": "fsNas1",
    }
    resource.update(site_id="site-1", settings=settings)

    method, url, kwargs = http.requests[0]
    assert method == "PATCH"
    assert "/openapi/v1/OMADACID/" in url
    assert url.endswith("/sites/site-1/dot1x")
    # Body passed through unchanged (dict-first; the workflow layer builds it).
    assert kwargs["json"] == settings
