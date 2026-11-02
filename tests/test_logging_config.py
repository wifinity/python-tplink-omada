from __future__ import annotations

import json

from omada_client.logging_config import format_body, mask_sensitive_body


def test_masks_nested_device_account_password() -> None:
    body = {"name": "SITE1", "deviceAccountSetting": {"username": "admin", "password": "hunter2"}}

    rendered = format_body(body)

    assert "hunter2" not in rendered
    assert json.loads(rendered) == {"name": "SITE1", "deviceAccountSetting": {"username": "admin", "password": "***"}}


def test_masks_keys_in_lists_of_dicts() -> None:
    body = {"authServer": [{"radiusServerIp": "10.0.0.1", "radiusPwd": "s3cr3t"}]}

    assert mask_sensitive_body(body) == {"authServer": [{"radiusServerIp": "10.0.0.1", "radiusPwd": "***"}]}


def test_masks_key_variants() -> None:
    body = {
        "client_secret": "a",
        "clientSecret": "b",
        "psk": "c",
        "communityString": "d",
        "authKey": "e",
        "access_token": "f",
    }

    assert set(mask_sensitive_body(body).values()) == {"***"}


def test_leaves_non_sensitive_keys_and_original_untouched() -> None:
    body = {"name": "SITE1", "ppskProfileId": "p1", "targetSites": ["s1"], "password": "x"}

    masked = mask_sensitive_body(body)

    assert masked == {"name": "SITE1", "ppskProfileId": "p1", "targetSites": ["s1"], "password": "***"}
    assert body["password"] == "x"


def test_non_dict_bodies_pass_through() -> None:
    assert format_body(None) == ""
    assert format_body(["a", 1]) == '["a", 1]'
    assert format_body("text") == '"text"'
