from __future__ import annotations

import pytest

from omada_client.exceptions import RadiusProfileNotFoundError
from omada_client.resources.radius_profiles import RadiusProfilesResource

_AUTH_SERVER = {"radiusServerIp": "10.140.0.10", "radiusPort": 1812, "radiusPwd": "s3cr3t"}


class DummyClient:
    def __init__(self) -> None:
        self.get_response: dict = {}
        self.get_responses: list | None = None
        self.get_calls: list[tuple[str, object]] = []
        self.post_calls: list[tuple[str, object]] = []

    def get(self, path: str, params=None):
        self.get_calls.append((path, params))
        if isinstance(self.get_responses, list) and self.get_responses:
            return self.get_responses.pop(0)
        return self.get_response

    def post(self, path: str, json=None):
        self.post_calls.append((path, json))
        return {"ok": True}


def _list_response(*profiles):
    return {"result": {"data": list(profiles)}}


def test_all_returns_profile_list() -> None:
    client = DummyClient()
    client.get_response = _list_response({"name": "Home Networking Wi-Fi", "radiusProfileId": "r1"})
    resource = RadiusProfilesResource(client)

    result = resource.all(site_id="s1")

    assert result == [{"name": "Home Networking Wi-Fi", "radiusProfileId": "r1"}]
    assert client.get_calls[0][0] == "/openapi/v1/sites/s1/profiles/radius"


def test_all_returns_empty_list_on_empty_response() -> None:
    client = DummyClient()
    client.get_response = {"result": {"data": []}}
    resource = RadiusProfilesResource(client)

    assert resource.all(site_id="s1") == []


def test_get_by_name_returns_matching_profile() -> None:
    client = DummyClient()
    client.get_response = _list_response(
        {"name": "Other", "radiusProfileId": "r0"},
        {"name": "Home Networking Wi-Fi", "radiusProfileId": "r1"},
    )
    resource = RadiusProfilesResource(client)

    result = resource.get(site_id="s1", name="Home Networking Wi-Fi")

    assert result == {"name": "Home Networking Wi-Fi", "radiusProfileId": "r1"}


def test_get_by_name_raises_when_not_found() -> None:
    client = DummyClient()
    client.get_response = _list_response({"name": "Other", "radiusProfileId": "r0"})
    resource = RadiusProfilesResource(client)

    with pytest.raises(RadiusProfileNotFoundError, match="Home Networking Wi-Fi"):
        resource.get(site_id="s1", name="Home Networking Wi-Fi")


def test_get_by_name_raises_on_duplicates() -> None:
    client = DummyClient()
    client.get_response = _list_response(
        {"name": "Home Networking Wi-Fi", "radiusProfileId": "r1"},
        {"name": "Home Networking Wi-Fi", "radiusProfileId": "r2"},
    )
    resource = RadiusProfilesResource(client)

    with pytest.raises(ValueError, match="Multiple RADIUS profiles"):
        resource.get(site_id="s1", name="Home Networking Wi-Fi")


def test_get_by_id_returns_matching_profile() -> None:
    client = DummyClient()
    client.get_response = _list_response(
        {"name": "Other", "radiusProfileId": "r0"},
        {"name": "Home Networking Wi-Fi", "radiusProfileId": "r1"},
    )
    resource = RadiusProfilesResource(client)

    result = resource.get(site_id="s1", id="r1")

    assert result["radiusProfileId"] == "r1"


def test_get_by_id_raises_when_not_found() -> None:
    client = DummyClient()
    client.get_response = _list_response({"name": "Other", "radiusProfileId": "r0"})
    resource = RadiusProfilesResource(client)

    with pytest.raises(RadiusProfileNotFoundError, match="r1"):
        resource.get(site_id="s1", id="r1")


def test_get_rejects_invalid_selector_combinations() -> None:
    client = DummyClient()
    resource = RadiusProfilesResource(client)

    with pytest.raises(ValueError, match="Provide exactly one"):
        resource.get(site_id="s1")

    with pytest.raises(ValueError, match="Provide exactly one"):
        resource.get(site_id="s1", id="r1", name="Home Networking Wi-Fi")


def test_create_posts_to_expected_path() -> None:
    client = DummyClient()
    resource = RadiusProfilesResource(client)

    resource.create(
        site_id="s1",
        name="Home Networking Wi-Fi",
        auth_servers=[_AUTH_SERVER],
    )

    assert len(client.post_calls) == 1
    path, payload = client.post_calls[0]
    assert path == "/openapi/v1/sites/s1/profiles/radius"
    assert payload["name"] == "Home Networking Wi-Fi"
    assert payload["authServer"] == [_AUTH_SERVER]
    assert payload["radiusAccountingEnable"] is False
    assert payload["wirelessVlanAssignment"] is False


def test_create_passes_accounting_and_vlan_flags() -> None:
    client = DummyClient()
    resource = RadiusProfilesResource(client)

    resource.create(
        site_id="s1",
        name="Test",
        auth_servers=[_AUTH_SERVER],
        accounting_enabled=True,
        wireless_vlan_assignment=True,
    )

    _, payload = client.post_calls[0]
    assert payload["radiusAccountingEnable"] is True
    assert payload["wirelessVlanAssignment"] is True


def test_create_raises_on_empty_name() -> None:
    client = DummyClient()
    resource = RadiusProfilesResource(client)

    with pytest.raises(ValueError, match="name must be a non-empty string"):
        resource.create(site_id="s1", name="", auth_servers=[_AUTH_SERVER])


def test_create_raises_on_empty_auth_servers() -> None:
    client = DummyClient()
    resource = RadiusProfilesResource(client)

    with pytest.raises(ValueError, match="auth_servers must be a non-empty list"):
        resource.create(site_id="s1", name="Test", auth_servers=[])


def test_upsert_creates_when_absent() -> None:
    client = DummyClient()
    client.get_response = _list_response()
    resource = RadiusProfilesResource(client)

    _, created = resource.upsert(
        site_id="s1",
        name="Home Networking Wi-Fi",
        auth_servers=[_AUTH_SERVER],
    )

    assert created is True
    assert len(client.post_calls) == 1
    assert client.post_calls[0][1]["name"] == "Home Networking Wi-Fi"


def test_upsert_skips_when_profile_exists() -> None:
    client = DummyClient()
    client.get_response = _list_response({"name": "Home Networking Wi-Fi", "radiusProfileId": "r1"})
    resource = RadiusProfilesResource(client)

    profile, created = resource.upsert(
        site_id="s1",
        name="Home Networking Wi-Fi",
        auth_servers=[_AUTH_SERVER],
    )

    assert created is False
    assert profile["radiusProfileId"] == "r1"
    assert len(client.post_calls) == 0
