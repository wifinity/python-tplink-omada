"""Shared helper for resource wrappers."""

from __future__ import annotations

from typing import Any, cast

# The 6.3 controller rejects pageSize > 100 on grid endpoints even where the spec allows 1000.
_DEFAULT_PAGE_SIZE = 100


class BaseResource:
    def __init__(self, client: Any, path: str) -> None:
        self.client = client
        self.path = path

    def list(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        payload = self.client.get(self.path, params=params or {})
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            data = payload.get("data") or payload.get("result") or payload.get("items")
            if isinstance(data, list):
                return data
        return []


def fetch_all_pages(
    client: Any,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> list[dict[str, Any]]:
    """GET every page of an Omada grid endpoint (``result.data`` + ``result.totalRows``).

    Stops on an empty page, a short page, or once ``totalRows`` items are collected.
    """
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        query: dict[str, Any] = dict(params or {})
        query["page"] = page
        query["pageSize"] = page_size
        response = cast(dict[str, Any], client.get(path, params=query))
        result = response.get("result")
        data = result.get("data") if isinstance(result, dict) else None
        if not isinstance(data, list) or not data:
            break
        items.extend(item for item in data if isinstance(item, dict))
        total = result.get("totalRows") if isinstance(result, dict) else None
        if len(data) < page_size or (isinstance(total, int) and len(items) >= total):
            break
        page += 1
    return items
