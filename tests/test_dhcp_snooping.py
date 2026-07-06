"""Unit tests for DhcpSnoopingResource.

Mirrors the DummyHttpClient capture pattern in test_switches.py: set the canned
response, call the method, assert on the captured (method, url, kwargs) tuple.
The create-body wrapper (``{"devices": [...]}``) is the key regression lock — the
controller silently no-ops a bare body (see the resource docstring).
"""

from omada_client.resources import DhcpSnoopingResource


class DummyHttpClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict]] = []
        self._get_response: dict = {}
        self._post_response: dict = {"errorCode": 0}
        self._patch_response: dict = {"errorCode": 0}
        self._delete_response: dict = {"errorCode": 0}

    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/OMADACID/").replace("/openapi/v2/", "/openapi/v2/OMADACID/")

    def get(self, url: str, **kwargs) -> dict:
        self.requests.append(("GET", url, kwargs))
        return self._get_response

    def post(self, url: str, **kwargs) -> dict:
        self.requests.append(("POST", url, kwargs))
        return self._post_response

    def patch(self, url: str, **kwargs) -> dict:
        self.requests.append(("PATCH", url, kwargs))
        return self._patch_response

    def delete(self, url: str, **kwargs) -> dict:
        self.requests.append(("DELETE", url, kwargs))
        return self._delete_response


def test_get_status_returns_enable_flag() -> None:
    http = DummyHttpClient()
    http._get_response = {"errorCode": 0, "result": {"dhcpSnoopEnable": True}}
    resource = DhcpSnoopingResource(http)

    assert resource.get_status(site_id="site-1") is True

    method, url, _ = http.requests[0]
    assert method == "GET"
    assert "/openapi/v1/OMADACID/" in url
    assert url.endswith("/sites/site-1/dhcpSnoops/status")


def test_get_status_defaults_false_when_absent() -> None:
    http = DummyHttpClient()
    http._get_response = {"errorCode": 0, "result": {}}
    resource = DhcpSnoopingResource(http)

    assert resource.get_status(site_id="site-1") is False


def test_set_status_patches_enable_body() -> None:
    http = DummyHttpClient()
    resource = DhcpSnoopingResource(http)

    resource.set_status(site_id="site-1", enabled=True)

    method, url, kwargs = http.requests[0]
    assert method == "PATCH"
    assert url.endswith("/sites/site-1/dhcpSnoops/status")
    assert kwargs["json"] == {"dhcpSnoopEnable": True}


def test_get_snoops_returns_result_data_with_paging() -> None:
    http = DummyHttpClient()
    http._get_response = {
        "errorCode": 0,
        "result": {"totalRows": 1, "data": [{"id": "s1", "mac": "AA-BB-CC-DD-EE-11", "ports": [{"port": 5}]}]},
    }
    resource = DhcpSnoopingResource(http)

    snoops = resource.get_snoops(site_id="site-1")

    assert snoops == [{"id": "s1", "mac": "AA-BB-CC-DD-EE-11", "ports": [{"port": 5}]}]
    method, url, kwargs = http.requests[0]
    assert method == "GET"
    assert url.endswith("/sites/site-1/dhcpSnoops")
    assert kwargs["params"] == {"page": 1, "pageSize": 1000}


def test_get_supported_hits_support_endpoint() -> None:
    http = DummyHttpClient()
    http._get_response = {"errorCode": 0, "result": {"data": [{"mac": "AA-BB-CC-DD-EE-11"}]}}
    resource = DhcpSnoopingResource(http)

    supported = resource.get_supported(site_id="site-1")

    assert supported == [{"mac": "AA-BB-CC-DD-EE-11"}]
    method, url, kwargs = http.requests[0]
    assert method == "GET"
    assert url.endswith("/sites/site-1/switches/supportDhcpSnoop")
    assert kwargs["params"] == {"page": 1, "pageSize": 1000}


def test_create_snoops_wraps_devices_envelope() -> None:
    http = DummyHttpClient()
    resource = DhcpSnoopingResource(http)

    devices = [{"mac": "AA-BB-CC-DD-EE-11", "ports": [{"port": 5}]}]
    resource.create_snoops(site_id="site-1", devices=devices)

    method, url, kwargs = http.requests[0]
    assert method == "POST"
    assert "/openapi/v1/OMADACID/" in url
    assert url.endswith("/sites/site-1/dhcpSnoops")
    # The mandatory top-level wrapper — without it the controller silently no-ops.
    assert kwargs["json"] == {"devices": [{"mac": "AA-BB-CC-DD-EE-11", "ports": [{"port": 5}]}]}


def test_update_snoop_patches_flat_body_at_id() -> None:
    http = DummyHttpClient()
    resource = DhcpSnoopingResource(http)

    settings = {"mac": "AA-BB-CC-DD-EE-11", "name": "AA-BB-CC-DD-EE-11", "ports": [{"port": 5}, {"port": 6}]}
    resource.update_snoop(site_id="site-1", snoop_id="snoop-9", settings=settings)

    method, url, kwargs = http.requests[0]
    assert method == "PATCH"
    assert url.endswith("/sites/site-1/dhcpSnoops/snoop-9")
    assert kwargs["json"] == settings  # flat, no devices wrapper


def test_delete_snoop_deletes_at_id() -> None:
    http = DummyHttpClient()
    resource = DhcpSnoopingResource(http)

    resource.delete_snoop(site_id="site-1", snoop_id="snoop-9")

    method, url, _ = http.requests[0]
    assert method == "DELETE"
    assert url.endswith("/sites/site-1/dhcpSnoops/snoop-9")


def test_find_snoop_by_mac_matches_regardless_of_format() -> None:
    http = DummyHttpClient()
    http._get_response = {"errorCode": 0, "result": {"data": [{"id": "s1", "mac": "AA-BB-CC-DD-EE-11"}]}}
    resource = DhcpSnoopingResource(http)

    # colon-form input matches the hyphen-form entry
    found = resource.find_snoop_by_mac(site_id="site-1", mac="aa:bb:cc:dd:ee:11")
    assert found is not None
    assert found["id"] == "s1"


def test_find_snoop_by_mac_returns_none_when_absent() -> None:
    http = DummyHttpClient()
    http._get_response = {"errorCode": 0, "result": {"data": [{"id": "s1", "mac": "AA-BB-CC-DD-EE-FF"}]}}
    resource = DhcpSnoopingResource(http)

    assert resource.find_snoop_by_mac(site_id="site-1", mac="aa:bb:cc:dd:ee:11") is None
