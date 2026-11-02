from __future__ import annotations

import pytest

from omada_client import OmadaClient
from omada_client.exceptions import FirmwareNotFoundError
from omada_client.resources.firmwares import FirmwaresResource

_LIST_PATH = "/openapi/v1/upgrade/firmwares"


class DummyClient:
    def __init__(self) -> None:
        self.get_responses: dict[str, list[dict]] = {}
        self.get_calls: list[tuple[str, object]] = []
        self.post_calls: list[tuple[str, object]] = []

    def get(self, path: str, params=None):
        self.get_calls.append((path, params))
        queue = self.get_responses.get(path, [])
        if len(queue) > 1:
            return queue.pop(0)
        return queue[0] if queue else {}

    def post(self, path: str, json=None):
        self.post_calls.append((path, json))
        return {"errorCode": 0}


def _firmware(id: str, description: str = "") -> dict:
    return {
        "id": id,
        "name": f"{id}.bin",
        "description": description,
        "modelTypeInfo": {"showModel": "EAP725-Wall(EU) v1.0"},
    }


def _grid(*items: dict, total: int | None = None) -> dict:
    return {"result": {"data": list(items), "totalRows": len(items) if total is None else total}}


def _targets(*site_ids: str) -> dict:
    return {"result": {"targetSites": [{"id": s, "name": f"name-{s}"} for s in site_ids]}}


def test_all_returns_every_page() -> None:
    client = DummyClient()
    first = [_firmware(f"f{i}") for i in range(100)]
    client.get_responses[_LIST_PATH] = [_grid(*first, total=101), _grid(_firmware("f100"), total=101)]

    result = FirmwaresResource(client).all()

    assert [item["id"] for item in result] == [f"f{i}" for i in range(101)]
    assert [params["page"] for _, params in client.get_calls] == [1, 2]
    assert client.get_calls[0][1]["pageSize"] == 100


def test_all_uses_omadac_prefixed_path() -> None:
    client = OmadaClient(base_url="https://omada.example", omadac_id="cid", client_id="x", client_secret="y")
    seen: list[str] = []
    client.get = lambda path, params=None: seen.append(path) or _grid()  # type: ignore[method-assign]

    client.firmwares.all()

    assert seen == ["/openapi/v1/cid/upgrade/firmwares"]


def test_get_returns_matching_file() -> None:
    client = DummyClient()
    client.get_responses[_LIST_PATH] = [_grid(_firmware("f1"), _firmware("f2"))]

    assert FirmwaresResource(client).get(id="f2")["id"] == "f2"


def test_get_raises_when_missing() -> None:
    client = DummyClient()
    client.get_responses[_LIST_PATH] = [_grid(_firmware("f1"))]

    with pytest.raises(FirmwareNotFoundError, match="f9"):
        FirmwaresResource(client).get(id="f9")


def test_get_target_sites_parses_result() -> None:
    client = DummyClient()
    client.get_responses[f"{_LIST_PATH}/f1/target-sites"] = [_targets("s1", "s2")]

    result = FirmwaresResource(client).get_target_sites(id="f1")

    assert result == [{"id": "s1", "name": "name-s1"}, {"id": "s2", "name": "name-s2"}]


@pytest.mark.parametrize("response", [{"result": {}}, {"result": {"targetSites": None}}, {}])
def test_get_target_sites_empty_when_missing(response: dict) -> None:
    client = DummyClient()
    client.get_responses[f"{_LIST_PATH}/f1/target-sites"] = [response]

    assert FirmwaresResource(client).get_target_sites(id="f1") == []


def test_set_target_sites_sends_full_list_and_preserves_description() -> None:
    client = DummyClient()
    client.get_responses[_LIST_PATH] = [_grid(_firmware("f1", description="pinned"))]

    FirmwaresResource(client).set_target_sites(id="f1", site_ids=["s1", "s2"])

    assert client.post_calls == [
        (f"{_LIST_PATH}/f1", {"targetEnable": True, "targetSites": ["s1", "s2"], "description": "pinned"})
    ]


def test_set_target_sites_empty_list_disables_targets() -> None:
    client = DummyClient()

    FirmwaresResource(client).set_target_sites(id="f1", site_ids=[], description="d")

    assert client.post_calls == [(f"{_LIST_PATH}/f1", {"targetEnable": False, "targetSites": [], "description": "d"})]
    assert client.get_calls == []


def test_set_target_sites_raises_for_unknown_file_without_description() -> None:
    client = DummyClient()
    client.get_responses[_LIST_PATH] = [_grid()]

    with pytest.raises(FirmwareNotFoundError):
        FirmwaresResource(client).set_target_sites(id="f1", site_ids=["s1"])
    assert client.post_calls == []


def test_add_target_site_appends_to_existing_list() -> None:
    client = DummyClient()
    client.get_responses[f"{_LIST_PATH}/f1/target-sites"] = [_targets("s1")]
    client.get_responses[_LIST_PATH] = [_grid(_firmware("f1", description="d"))]

    assert FirmwaresResource(client).add_target_site(id="f1", site_id="s2") is True
    assert client.post_calls == [
        (f"{_LIST_PATH}/f1", {"targetEnable": True, "targetSites": ["s1", "s2"], "description": "d"})
    ]


def test_add_target_site_noop_when_present() -> None:
    client = DummyClient()
    client.get_responses[f"{_LIST_PATH}/f1/target-sites"] = [_targets("s1", "s2")]

    assert FirmwaresResource(client).add_target_site(id="f1", site_id="s2") is False
    assert client.post_calls == []


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("get", ("f1",)),
        ("get_target_sites", ("f1",)),
        ("set_target_sites", ("f1", ["s1"])),
        ("add_target_site", ("f1", "s1")),
    ],
)
def test_methods_are_keyword_only(method: str, args: tuple) -> None:
    with pytest.raises(TypeError):
        getattr(FirmwaresResource(DummyClient()), method)(*args)
