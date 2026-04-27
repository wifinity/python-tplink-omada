from __future__ import annotations

import pytest

from omada_client.resources.sites import SitesResource


class DummyClient:
    def __init__(self) -> None:
        self.last_path = ""
        self.last_params = None
        self.last_json = None
        self.get_response = {"ok": True}
        self.get_responses = None
        self.get_calls: list[tuple[str, object]] = []

    def post(self, path: str, json):
        self.last_path = path
        self.last_json = json
        return {"ok": True}

    def put(self, path: str, json):
        self.last_path = path
        self.last_json = json
        return {"result": {"siteId": "site-1", **json}}

    def get(self, path: str, params=None):
        self.last_path = path
        self.last_params = params
        self.get_calls.append((path, params))
        if isinstance(self.get_responses, list) and self.get_responses:
            return self.get_responses.pop(0)
        return self.get_response


def test_create_site_defaults_with_explicit_device_credentials() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    result = resource.create(
        name="SiteA",
        device_username="admin",
        device_password="StrongPassword!123",
    )

    assert result == {"ok": True}
    assert client.last_path == "/openapi/v1/sites"
    assert client.last_json["name"] == "SiteA"
    assert client.last_json["region"] == "United Kingdom"
    assert client.last_json["scenario"] == "Dormitory"
    assert client.last_json["timeZone"] == "UTC"
    assert client.last_json["deviceAccountSetting"] == {
        "username": "admin",
        "password": "StrongPassword!123",
    }


def test_create_site_allows_overrides() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    resource.create(
        name="SiteA",
        region="United States",
        scenario="Work",
        time_zone="Europe/London",
        device_username="override-user",
        device_password="OverridePassword!123",
        tagIds=["tag-1"],
    )

    assert client.last_json["region"] == "United States"
    assert client.last_json["scenario"] == "Work"
    assert client.last_json["timeZone"] == "Europe/London"
    assert client.last_json["tagIds"] == ["tag-1"]
    assert client.last_json["deviceAccountSetting"] == {
        "username": "override-user",
        "password": "OverridePassword!123",
    }


def test_create_site_accepts_device_account_setting_from_kwargs() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    resource.create(
        name="SiteA",
        deviceAccountSetting={"username": "raw-user", "password": "RawPassword!123"},
    )

    assert client.last_json["deviceAccountSetting"] == {
        "username": "raw-user",
        "password": "RawPassword!123",
    }


def test_create_site_explicit_device_credentials_override_kwargs() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    resource.create(
        name="SiteA",
        device_username="explicit-user",
        device_password="ExplicitPassword!123",
        deviceAccountSetting={"username": "raw-user", "password": "RawPassword!123"},
    )

    assert client.last_json["deviceAccountSetting"] == {
        "username": "explicit-user",
        "password": "ExplicitPassword!123",
    }


def test_create_site_requires_device_account_setting() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    with pytest.raises(ValueError, match="deviceAccountSetting is required"):
        resource.create(name="SiteA")


def test_create_site_requires_both_device_username_and_device_password() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    with pytest.raises(ValueError, match="device_username and device_password must be provided together"):
        resource.create(name="SiteA", device_username="admin")

    with pytest.raises(ValueError, match="device_username and device_password must be provided together"):
        resource.create(name="SiteA", device_password="StrongPassword!123")


def test_create_site_region_validation_accepts_full_name_case_insensitive() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    resource.create(
        name="SiteA",
        region="united kingdom",
        device_username="admin",
        device_password="StrongPassword!123",
    )

    assert client.last_json["region"] == "united kingdom"


def test_create_site_region_validation_rejects_iso_codes() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    with pytest.raises(ValueError, match="Country code 'GB' is not accepted"):
        resource.create(
            name="SiteA",
            region="GB",
            device_username="admin",
            device_password="StrongPassword!123",
        )

    with pytest.raises(ValueError, match="Country code 'GBR' is not accepted"):
        resource.create(
            name="SiteA",
            region="GBR",
            device_username="admin",
            device_password="StrongPassword!123",
        )


def test_create_site_region_validation_rejects_invalid_country_name() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    with pytest.raises(ValueError, match="Invalid country name 'United Kingdon'"):
        resource.create(
            name="SiteA",
            region="United Kingdon",
            device_username="admin",
            device_password="StrongPassword!123",
        )


def test_create_site_region_validation_requires_non_empty_string() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    with pytest.raises(ValueError, match="region must be a non-empty string"):
        resource.create(
            name="SiteA",
            region="",
            device_username="admin",
            device_password="StrongPassword!123",
        )


class OmadacPathDummyClient(DummyClient):
    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/omadac-1/")


def test_create_site_uses_api_path_rewrite() -> None:
    client = OmadacPathDummyClient()
    resource = SitesResource(client)

    resource.create(
        name="SiteA",
        device_username="admin",
        device_password="StrongPassword!123",
    )

    assert client.last_path == "/openapi/v1/omadac-1/sites"


def test_update_site_maps_timezone_and_returns_result() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    result = resource.update(
        id="site-1",
        name="Updated Site",
        region="United Kingdom",
        scenario="Work",
        timezone="Europe/London",
        device_username="admin",
        device_password="StrongPassword!123",
    )

    assert client.last_path == "/openapi/v1/sites/site-1"
    assert client.last_json == {
        "name": "Updated Site",
        "region": "United Kingdom",
        "scenario": "Work",
        "timeZone": "Europe/London",
        "deviceAccountSetting": {
            "username": "admin",
            "password": "StrongPassword!123",
        },
    }
    assert result == {
        "siteId": "site-1",
        "name": "Updated Site",
        "region": "United Kingdom",
        "scenario": "Work",
        "timeZone": "Europe/London",
        "deviceAccountSetting": {
            "username": "admin",
            "password": "StrongPassword!123",
        },
    }


def test_update_site_requires_both_device_username_and_device_password() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    with pytest.raises(ValueError, match="device_username and device_password must be provided together"):
        resource.update(id="site-1", device_username="admin")

    with pytest.raises(ValueError, match="device_username and device_password must be provided together"):
        resource.update(id="site-1", device_password="StrongPassword!123")


def test_update_site_region_validation_rejects_invalid_country_name() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    with pytest.raises(ValueError, match="Invalid country name 'United Kingdon'"):
        resource.update(id="site-1", region="United Kingdon")


def test_update_site_uses_api_path_rewrite() -> None:
    client = OmadacPathDummyClient()
    resource = SitesResource(client)

    resource.update(id="site-1", timezone="UTC")

    assert client.last_path == "/openapi/v1/omadac-1/sites/site-1"


def test_update_site_applies_create_defaults_when_values_omitted() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    result = resource.update(id="site-1")

    assert client.last_json == {
        "region": "United Kingdom",
        "scenario": "Dormitory",
        "timeZone": "UTC",
    }
    assert result == {
        "siteId": "site-1",
        "region": "United Kingdom",
        "scenario": "Dormitory",
        "timeZone": "UTC",
    }


def test_update_site_explicit_values_override_defaults() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    resource.update(
        id="site-1",
        region="United States",
        scenario="Work",
        timezone="Europe/London",
    )

    assert client.last_json["region"] == "United States"
    assert client.last_json["scenario"] == "Work"
    assert client.last_json["timeZone"] == "Europe/London"


def test_all_sites_returns_result_data_list() -> None:
    client = DummyClient()
    client.get_response = {"result": {"data": [{"siteId": "site-1", "name": "Main Site"}]}}
    resource = SitesResource(client)

    result = resource.all()

    assert result == [{"siteId": "site-1", "name": "Main Site"}]
    assert client.last_path == "/openapi/v1/sites"
    assert client.last_params == {"page": 1, "pageSize": 1000}


def test_all_sites_passes_query_params() -> None:
    client = DummyClient()
    client.get_response = {"result": {"data": []}}
    resource = SitesResource(client)

    resource.all(params={"searchKey": "Main Site", "page": 2})

    assert client.last_path == "/openapi/v1/sites"
    assert client.last_params == {"searchKey": "Main Site", "page": 2, "pageSize": 1000}


def test_get_site_by_id_uses_site_endpoint() -> None:
    client = DummyClient()
    client.get_response = {"result": {"siteId": "site-1", "name": "Main Site"}}
    resource = SitesResource(client)

    result = resource.get(id="site-1")

    assert result == {"siteId": "site-1", "name": "Main Site"}
    assert client.last_path == "/openapi/v1/sites/site-1"
    assert client.last_params is None


def test_get_site_by_name_uses_list_search_and_exact_match() -> None:
    client = DummyClient()
    client.get_responses = [
        {
            "result": {
                "data": [
                    {"siteId": "site-1", "name": "Main Site"},
                    {"siteId": "site-2", "name": "Backup Site"},
                ]
            }
        },
        {"result": {"siteId": "site-1", "name": "Main Site", "ntpEnable": False}},
    ]
    resource = SitesResource(client)

    result = resource.get(name="Main Site")

    assert result == {"siteId": "site-1", "name": "Main Site", "ntpEnable": False}
    assert client.get_calls[0] == (
        "/openapi/v1/sites",
        {"searchKey": "Main Site", "page": 1, "pageSize": 1000},
    )
    assert client.get_calls[1] == ("/openapi/v1/sites/site-1", None)


def test_get_site_rejects_invalid_selector_combinations() -> None:
    client = DummyClient()
    resource = SitesResource(client)

    with pytest.raises(ValueError, match="Provide exactly one of 'id' or 'name'"):
        resource.get()

    with pytest.raises(ValueError, match="Provide exactly one of 'id' or 'name'"):
        resource.get(id="site-1", name="Main Site")


def test_get_site_by_name_raises_when_not_found() -> None:
    client = DummyClient()
    client.get_response = {"result": {"data": [{"siteId": "site-2", "name": "Other Site"}]}}
    resource = SitesResource(client)

    with pytest.raises(ValueError, match="Site with name 'Main Site' was not found"):
        resource.get(name="Main Site")


def test_get_site_by_name_raises_when_multiple_exact_matches() -> None:
    client = DummyClient()
    client.get_response = {
        "result": {
            "data": [
                {"siteId": "site-1", "name": "Main Site"},
                {"siteId": "site-2", "name": "Main Site"},
            ]
        }
    }
    resource = SitesResource(client)

    with pytest.raises(ValueError, match="Multiple sites found with name 'Main Site'"):
        resource.get(name="Main Site")


def test_get_site_by_name_raises_when_site_id_missing() -> None:
    client = DummyClient()
    client.get_response = {"result": {"data": [{"name": "Main Site"}]}}
    resource = SitesResource(client)

    with pytest.raises(ValueError, match="Matched site 'Main Site' does not include a valid siteId"):
        resource.get(name="Main Site")


def test_all_and_get_use_api_path_rewrite() -> None:
    client = OmadacPathDummyClient()
    client.get_response = {"result": {"data": [{"siteId": "site-1", "name": "Main Site"}]}}
    resource = SitesResource(client)

    resource.all()
    assert client.last_path == "/openapi/v1/omadac-1/sites"

    client.get_response = {"result": {"siteId": "site-1", "name": "Main Site"}}
    resource.get(id="site-1")
    assert client.last_path == "/openapi/v1/omadac-1/sites/site-1"
