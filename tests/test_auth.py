from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from omada_client.auth import OAuth2TokenManager
from omada_client.exceptions import OmadaAuthenticationError


class DummyResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self) -> dict:
        return self._payload


def test_token_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        return DummyResponse(200, {"access_token": "abc", "expires_in": 3600})

    monkeypatch.setattr(httpx, "post", fake_post)

    mgr = OAuth2TokenManager("https://token", "id", "secret", omadac_id="omadac-1")
    t1 = mgr.get_token()
    t2 = mgr.get_token()

    assert t1 == "abc"
    assert t2 == "abc"
    assert calls["count"] == 1


def test_missing_access_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*args, **kwargs):
        return DummyResponse(200, {"expires_in": 3600})

    monkeypatch.setattr(httpx, "post", fake_post)

    mgr = OAuth2TokenManager("https://token", "id", "secret", omadac_id="omadac-1")
    with pytest.raises(OmadaAuthenticationError):
        mgr.get_token()


def test_token_expired_triggers_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        return DummyResponse(200, {"access_token": f"abc{calls['count']}", "expires_in": 10})

    monkeypatch.setattr(httpx, "post", fake_post)

    mgr = OAuth2TokenManager("https://token", "id", "secret", omadac_id="omadac-1", token_refresh_buffer=0)
    first = mgr.get_token()
    mgr._token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    second = mgr.get_token()

    assert first != second
    assert calls["count"] == 2


def test_token_request_uses_query_and_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return DummyResponse(
            200,
            {
                "errorCode": 0,
                "result": {"accessToken": "local-token", "expiresIn": 7200},
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    mgr = OAuth2TokenManager(
        "https://token",
        "id",
        "secret",
        omadac_id="omadac-1",
    )
    token = mgr.get_token()

    assert token == "local-token"
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["params"] == {"grant_type": "client_credentials"}
    assert kwargs["json"] == {
        "omadacId": "omadac-1",
        "client_id": "id",
        "client_secret": "secret",
    }
    assert kwargs["headers"] == {"Content-Type": "application/json"}


def test_error_code_raises_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*args, **kwargs):
        return DummyResponse(200, {"errorCode": -1001, "msg": "Invalid request parameters."})

    monkeypatch.setattr(httpx, "post", fake_post)

    mgr = OAuth2TokenManager(
        "https://token",
        "id",
        "secret",
        omadac_id="omadac-1",
    )
    with pytest.raises(OmadaAuthenticationError, match="errorCode=-1001"):
        mgr.get_token()


def test_headers_use_access_token_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*args, **kwargs):
        return DummyResponse(200, {"errorCode": 0, "result": {"accessToken": "abc", "expiresIn": 3600}})

    monkeypatch.setattr(httpx, "post", fake_post)

    mgr = OAuth2TokenManager(
        "https://token",
        "id",
        "secret",
        omadac_id="omadac-1",
    )
    assert mgr.get_headers() == {"Authorization": "AccessToken=abc"}


def test_token_response_parses_root_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return DummyResponse(200, {"access_token": "abc", "expires_in": 3600})

    monkeypatch.setattr(httpx, "post", fake_post)

    mgr = OAuth2TokenManager(
        "https://token",
        "id",
        "secret",
        omadac_id="omadac-1",
    )
    assert mgr.get_token() == "abc"
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["params"] == {"grant_type": "client_credentials"}
    assert kwargs["json"] == {
        "omadacId": "omadac-1",
        "client_id": "id",
        "client_secret": "secret",
    }
