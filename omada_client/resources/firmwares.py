"""Uploaded firmware files and their Application Sites (controller-level)."""

from __future__ import annotations

from typing import Any, cast

from .base import fetch_all_pages


class FirmwaresResource:
    """Firmware files uploaded under "Upload Firmware for Update".

    Each file targets a single device model. Its target sites ("Application Sites") are the
    sites allowed to upgrade to it. The controller's edit call replaces the whole site list.
    """

    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    def all(self) -> list[dict[str, Any]]:
        """Return every uploaded firmware file (``id``, ``name``, ``description``, ``modelTypeInfo``)."""
        return fetch_all_pages(self.client, self._path("/openapi/v1/upgrade/firmwares"))

    def get(self, *, id: str) -> dict[str, Any]:
        from ..exceptions import FirmwareNotFoundError

        for item in self.all():
            if item.get("id") == id:
                return item
        raise FirmwareNotFoundError(f"Firmware file with id '{id}' was not found")

    def get_target_sites(self, *, id: str) -> list[dict[str, Any]]:
        """Return the firmware file's target sites as ``[{"id": ..., "name": ...}]``."""
        response = cast(
            dict[str, Any],
            self.client.get(self._path(f"/openapi/v1/upgrade/firmwares/{id}/target-sites")),
        )
        result = response.get("result")
        sites = result.get("targetSites") if isinstance(result, dict) else None
        if not isinstance(sites, list):
            return []
        return [site for site in sites if isinstance(site, dict)]

    def set_target_sites(
        self,
        *,
        id: str,
        site_ids: list[str],
        description: str | None = None,
    ) -> dict[str, Any]:
        """Replace the firmware file's target sites with ``site_ids``.

        The edit call also writes the file's description, so when ``description`` is omitted
        the current one is read back and resent unchanged.
        """
        if description is None:
            current = self.get(id=id).get("description")
            description = current if isinstance(current, str) else ""
        payload: dict[str, Any] = {
            "targetEnable": bool(site_ids),
            "targetSites": list(site_ids),
            "description": description,
        }
        response = self.client.post(
            self._path(f"/openapi/v1/upgrade/firmwares/{id}"),
            json=payload,
        )
        return cast(dict[str, Any], response)

    def add_target_site(self, *, id: str, site_id: str) -> bool:
        """Add ``site_id`` to the firmware file's target sites; return False if already present.

        Read-modify-write: a concurrent writer to the same file between the read and the
        write can drop this site or theirs. Callers that need certainty re-read afterwards.
        """
        current = [site.get("id") for site in self.get_target_sites(id=id)]
        site_ids = [site for site in current if isinstance(site, str) and site]
        if site_id in site_ids:
            return False
        self.set_target_sites(id=id, site_ids=[*site_ids, site_id])
        return True
