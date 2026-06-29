from __future__ import annotations

import pytest

from omada_client.resources.site_services import SiteServicesResource


class DummyClient:
    def __init__(self) -> None:
        self.get_response: dict = {}
        self.patch_path: str = ""
        self.patch_json: dict = {}
        self.patch_response: dict = {}

    def get(self, path: str, params=None) -> dict:
        self.last_get_path = path
        return self.get_response

    def patch(self, path: str, json=None) -> dict:
        self.patch_path = path
        self.patch_json = json or {}
        return self.patch_response

    def api_path(self, path: str) -> str:
        return path


def test_get_snmp_unwraps_result() -> None:
    client = DummyClient()
    client.get_response = {"result": {"snmpV1V2CEnable": True, "communityString": "public"}}
    resource = SiteServicesResource(client)

    result = resource.get_snmp(site_id="site-1")

    assert result["snmpV1V2CEnable"] is True
    assert result["communityString"] == "public"
    assert client.last_get_path == "/openapi/v1/sites/site-1/setting/service/snmp"


def test_get_snmp_no_result_wrapper_returns_response() -> None:
    client = DummyClient()
    client.get_response = {"snmpV1V2CEnable": False, "snmpV3Enable": False}
    resource = SiteServicesResource(client)

    result = resource.get_snmp(site_id="site-2")

    assert result["snmpV1V2CEnable"] is False


def test_update_snmp_v1v2c_only() -> None:
    client = DummyClient()
    client.patch_response = {"errorCode": 0}
    resource = SiteServicesResource(client)

    resource.update_snmp(
        site_id="site-1",
        snmpv1v2c_enable=True,
        snmpv3_enable=False,
        community_string="wifinity-mon",
    )

    assert client.patch_path == "/openapi/v1/sites/site-1/setting/service/snmp"
    assert client.patch_json["snmpV1V2CEnable"] is True
    assert client.patch_json["snmpV3Enable"] is False
    assert client.patch_json["communityString"] == "wifinity-mon"
    assert "username" not in client.patch_json
    assert "password" not in client.patch_json


def test_update_snmp_v3_only() -> None:
    client = DummyClient()
    client.patch_response = {"errorCode": 0}
    resource = SiteServicesResource(client)

    resource.update_snmp(
        site_id="site-1",
        snmpv1v2c_enable=False,
        snmpv3_enable=True,
        username="snmpv3user",
        password="authpassword123",
    )

    assert client.patch_json["snmpV1V2CEnable"] is False
    assert client.patch_json["snmpV3Enable"] is True
    assert client.patch_json["username"] == "snmpv3user"
    assert client.patch_json["password"] == "authpassword123"
    assert "communityString" not in client.patch_json


def test_update_snmp_both_disabled_omits_optional_fields() -> None:
    client = DummyClient()
    client.patch_response = {"errorCode": 0}
    resource = SiteServicesResource(client)

    resource.update_snmp(
        site_id="site-1",
        snmpv1v2c_enable=False,
        snmpv3_enable=False,
    )

    assert client.patch_json["snmpV1V2CEnable"] is False
    assert client.patch_json["snmpV3Enable"] is False
    assert "communityString" not in client.patch_json
    assert "username" not in client.patch_json
    assert "password" not in client.patch_json


def test_update_snmp_both_enabled() -> None:
    client = DummyClient()
    client.patch_response = {"errorCode": 0}
    resource = SiteServicesResource(client)

    resource.update_snmp(
        site_id="site-1",
        snmpv1v2c_enable=True,
        snmpv3_enable=True,
        community_string="public",
        username="admin",
        password="secret",
    )

    assert client.patch_json["snmpV1V2CEnable"] is True
    assert client.patch_json["snmpV3Enable"] is True
    assert client.patch_json["communityString"] == "public"
    assert client.patch_json["username"] == "admin"
    assert client.patch_json["password"] == "secret"
