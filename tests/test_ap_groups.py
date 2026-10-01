from __future__ import annotations

import pytest

from omada_client.exceptions import APGroupNotFoundError
from omada_client.resources.ap_groups import APGroupsResource


class DummyClient:
    def __init__(self) -> None:
        self.get_calls: list[tuple[str, object]] = []
        self.post_calls: list[tuple[str, object]] = []
        self.patch_calls: list[tuple[str, object]] = []
        self.delete_calls: list[str] = []
        self.get_responses: list[dict[str, object]] = []
        self.get_response: dict[str, object] = {"result": {"data": []}}

    def get(self, path: str, params=None):
        self.get_calls.append((path, params))
        if self.get_responses:
            return self.get_responses.pop(0)
        return self.get_response

    def post(self, path: str, json=None):
        self.post_calls.append((path, json))
        return {"errorCode": 0, "result": {"id": "g-new"}}

    def patch(self, path: str, json=None):
        self.patch_calls.append((path, json))
        return {"errorCode": 0}

    def delete(self, path: str, json=None):
        self.delete_calls.append(path)
        return {"errorCode": 0}


class OmadacPathDummyClient(DummyClient):
    def api_path(self, path: str) -> str:
        return path.replace("/openapi/v1/", "/openapi/v1/omadac-1/")


def _groups(*groups: tuple[str, str]) -> dict[str, object]:
    return {"result": {"data": [{"id": gid, "name": name} for gid, name in groups], "totalRows": len(groups)}}


def test_all_sends_pagination_and_search_key() -> None:
    client = DummyClient()
    client.get_response = _groups(("g1", "Corp"))

    result = APGroupsResource(client).all(site_id="s1", search_key="Corp")

    assert result == [{"id": "g1", "name": "Corp"}]
    assert client.get_calls == [("/openapi/v1/sites/s1/ap-groups", {"searchKey": "Corp", "page": 1, "pageSize": 100})]


def test_all_without_search_key_sends_only_pagination() -> None:
    client = DummyClient()

    APGroupsResource(client).all(site_id="s1")

    assert client.get_calls == [("/openapi/v1/sites/s1/ap-groups", {"page": 1, "pageSize": 100})]


def test_get_by_id_uses_info_endpoint() -> None:
    client = DummyClient()
    client.get_response = {"result": {"id": "g1", "name": "Corp", "apNum": 2}}

    result = APGroupsResource(client).get(site_id="s1", id="g1")

    assert result == {"id": "g1", "name": "Corp", "apNum": 2}
    assert client.get_calls == [("/openapi/v1/sites/s1/ap-groups/g1/info", None)]


def test_get_by_id_empty_result_raises_not_found() -> None:
    client = DummyClient()
    client.get_response = {"errorCode": 0, "result": {}}

    with pytest.raises(APGroupNotFoundError, match="id 'g1'"):
        APGroupsResource(client).get(site_id="s1", id="g1")


def test_get_by_name_exact_match_from_search() -> None:
    client = DummyClient()
    client.get_response = _groups(("g1", "Corp"), ("g2", "Corp Guest"))

    result = APGroupsResource(client).get(site_id="s1", name="Corp")

    assert result == {"id": "g1", "name": "Corp"}


def test_get_by_name_missing_raises_not_found() -> None:
    client = DummyClient()
    client.get_response = _groups(("g2", "Corp Guest"))

    with pytest.raises(APGroupNotFoundError, match="name 'Corp'"):
        APGroupsResource(client).get(site_id="s1", name="Corp")


def test_get_by_name_duplicate_raises_value_error() -> None:
    client = DummyClient()
    client.get_response = _groups(("g1", "Corp"), ("g2", "Corp"))

    with pytest.raises(ValueError, match="Multiple AP groups found with name 'Corp'"):
        APGroupsResource(client).get(site_id="s1", name="Corp")


def test_get_requires_exactly_one_selector() -> None:
    resource = APGroupsResource(DummyClient())

    with pytest.raises(ValueError, match="exactly one"):
        resource.get(site_id="s1")
    with pytest.raises(ValueError, match="exactly one"):
        resource.get(site_id="s1", id="g1", name="Corp")


def test_create_sends_name_and_normalized_macs() -> None:
    client = DummyClient()

    result = APGroupsResource(client).create(site_id="s1", name="Corp", ap_macs=["aa:bb:cc:dd:ee:ff"])

    assert result == {"errorCode": 0, "result": {"id": "g-new"}}
    assert client.post_calls == [("/openapi/v1/sites/s1/ap-groups", {"name": "Corp", "apMacs": ["AA-BB-CC-DD-EE-FF"]})]


def test_create_without_macs_sends_name_only() -> None:
    client = DummyClient()

    APGroupsResource(client).create(site_id="s1", name="Corp")

    assert client.post_calls == [("/openapi/v1/sites/s1/ap-groups", {"name": "Corp"})]


def test_create_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="name must be a non-empty string"):
        APGroupsResource(DummyClient()).create(site_id="s1", name="")


def test_update_by_id_fills_current_name() -> None:
    client = DummyClient()
    client.get_response = {"result": {"id": "g1", "name": "Corp"}}

    APGroupsResource(client).update(site_id="s1", id="g1", add_ap_macs=["aabbccddeeff"])

    assert client.patch_calls == [
        ("/openapi/v1/sites/s1/ap-groups/g1", {"name": "Corp", "addApMacs": ["AA-BB-CC-DD-EE-FF"]})
    ]


def test_update_by_name_renames_and_removes_macs() -> None:
    client = DummyClient()
    client.get_response = _groups(("g1", "Corp"))

    APGroupsResource(client).update(site_id="s1", name="Corp", new_name="Corp2", remove_ap_macs=["AA-BB-CC-DD-EE-FF"])

    assert client.patch_calls == [
        ("/openapi/v1/sites/s1/ap-groups/g1", {"name": "Corp2", "removeApMacs": ["AA-BB-CC-DD-EE-FF"]})
    ]


def test_update_requires_a_change() -> None:
    with pytest.raises(ValueError, match="at least one of"):
        APGroupsResource(DummyClient()).update(site_id="s1", id="g1")


def test_delete_by_id_skips_lookup() -> None:
    client = DummyClient()

    APGroupsResource(client).delete(site_id="s1", id="g1")

    assert client.get_calls == []
    assert client.delete_calls == ["/openapi/v1/sites/s1/ap-groups/g1"]


def test_delete_by_name_resolves_id() -> None:
    client = DummyClient()
    client.get_response = _groups(("g7", "Corp"))

    APGroupsResource(client).delete(site_id="s1", name="Corp")

    assert client.delete_calls == ["/openapi/v1/sites/s1/ap-groups/g7"]


def test_resolve_ids_matches_id_then_name_with_one_list_call() -> None:
    client = DummyClient()
    client.get_response = _groups(("g1", "Corp"), ("g2", "Guest APs"))

    ids = APGroupsResource(client).resolve_ids(site_id="s1", ap_groups=["Guest APs", "g1", "Corp"])

    assert ids == ["g2", "g1"]
    assert len(client.get_calls) == 1


def test_resolve_ids_unknown_raises_not_found() -> None:
    client = DummyClient()
    client.get_response = _groups(("g1", "Corp"))

    with pytest.raises(APGroupNotFoundError, match="'Missing'"):
        APGroupsResource(client).resolve_ids(site_id="s1", ap_groups=["Missing"])


def test_resolve_ids_rejects_empty_list() -> None:
    with pytest.raises(ValueError, match="non-empty list"):
        APGroupsResource(DummyClient()).resolve_ids(site_id="s1", ap_groups=[])


def test_methods_use_api_path_rewrite() -> None:
    client = OmadacPathDummyClient()
    resource = APGroupsResource(client)

    resource.create(site_id="s1", name="Corp")
    resource.delete(site_id="s1", id="g1")

    assert client.post_calls[0][0] == "/openapi/v1/omadac-1/sites/s1/ap-groups"
    assert client.delete_calls == ["/openapi/v1/omadac-1/sites/s1/ap-groups/g1"]
