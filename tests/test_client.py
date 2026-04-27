from __future__ import annotations

import httpx
import pytest

from omada_client import OmadaClient
from omada_client.exceptions import (
    OmadaAPIError,
    OmadaAuthenticationError,
    OmadaNotFoundError,
)


class DummyAuth:
    def __init__(self) -> None:
        self.cleared = False

    def get_headers(self) -> dict[str, str]:
        return {"Authorization": "AccessToken=token"}

    def clear_token(self) -> None:
        self.cleared = True


def _mock_http(response: httpx.Response) -> httpx.Client:
    return httpx.Client(
        base_url="https://controller.example",
        transport=httpx.MockTransport(lambda _: response),
    )


def test_successful_get_response() -> None:
    client = OmadaClient(
        base_url="https://controller.example",
        omadac_id="omadac-1",
        client_id="id",
        client_secret="secret",
    )
    client.auth = DummyAuth()  # type: ignore[assignment]
    client._http = _mock_http(httpx.Response(200, json={"ok": True}))

    payload = client.get("/openapi/v1/sites")

    assert payload == {"ok": True}


def test_successful_get_response_with_zero_error_code() -> None:
    client = OmadaClient(
        base_url="https://controller.example",
        omadac_id="omadac-1",
        client_id="id",
        client_secret="secret",
    )
    client.auth = DummyAuth()  # type: ignore[assignment]
    client._http = _mock_http(httpx.Response(200, json={"errorCode": 0, "result": {"ok": True}}))

    payload = client.get("/openapi/v1/sites")

    assert payload["errorCode"] == 0
    assert payload["result"] == {"ok": True}


def test_non_zero_error_code_on_200_raises_api_error() -> None:
    client = OmadaClient(
        base_url="https://controller.example",
        omadac_id="omadac-1",
        client_id="id",
        client_secret="secret",
    )
    client.auth = DummyAuth()  # type: ignore[assignment]
    client._http = _mock_http(
        httpx.Response(
            200,
            json={"errorCode": -30105, "msg": "Invalid password"},
        )
    )

    with pytest.raises(OmadaAPIError, match="Invalid password") as error_info:
        client.get("/openapi/v1/sites")

    assert error_info.value.response_data == {
        "errorCode": -30105,
        "msg": "Invalid password",
    }


def test_401_clears_token() -> None:
    client = OmadaClient(
        base_url="https://controller.example",
        omadac_id="omadac-1",
        client_id="id",
        client_secret="secret",
    )
    auth = DummyAuth()
    client.auth = auth  # type: ignore[assignment]
    client._http = _mock_http(httpx.Response(401, json={"message": "bad"}))

    with pytest.raises(OmadaAuthenticationError):
        client.get("/openapi/v1/sites")

    assert auth.cleared is True


def test_404_maps_to_not_found() -> None:
    client = OmadaClient(
        base_url="https://controller.example",
        omadac_id="omadac-1",
        client_id="id",
        client_secret="secret",
    )
    client.auth = DummyAuth()  # type: ignore[assignment]
    client._http = _mock_http(httpx.Response(404, json={"message": "missing"}))

    with pytest.raises(OmadaNotFoundError):
        client.get("/openapi/v1/sites/unknown")


def test_client_requires_omadac_id() -> None:
    with pytest.raises(ValueError, match="omadac_id is required"):
        OmadaClient(
            base_url="https://controller.example",
            omadac_id="",
            client_id="id",
            client_secret="secret",
        )


def test_api_path_includes_omadac_id_for_openapi_v1_paths() -> None:
    client = OmadaClient(
        base_url="https://controller.example",
        omadac_id="omadac-1",
        client_id="id",
        client_secret="secret",
    )

    assert client.api_path("/openapi/v1/sites") == "/openapi/v1/omadac-1/sites"
    assert client.api_path("/openapi/v1/omadac-1/sites") == "/openapi/v1/omadac-1/sites"
    assert client.api_path("/openapi/authorize/token") == "/openapi/authorize/token"


def test_client_exposes_aps_resource() -> None:
    client = OmadaClient(
        base_url="https://controller.example",
        omadac_id="omadac-1",
        client_id="id",
        client_secret="secret",
    )

    assert client.aps is not None
