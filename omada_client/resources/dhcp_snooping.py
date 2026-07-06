"""DHCP-snooping operations for an Omada site.

Omada models DHCP snooping in two layers:

- a **site-wide master enable** (``/dhcpSnoops/status``); and
- **per-device snoop entries** (``/dhcpSnoops``) listing the ports whose DHCP
  traffic is snooped — i.e. the client-facing / *untrusted* ports. The
  uplink/cascade port is auto-excluded (implicitly *trusted*) and surfaces in
  ``unSelectedablePorts`` on ``get_supported``.

Spec-vs-reality (verified live against ``SG2210XMP-M2 v1.0``; see the netstack hub
capability doc ``netstack/planning/dhcp-snooping-omada-api.md``):

- Create (``POST /dhcpSnoops``) requires the entries wrapped in a top-level
  ``devices`` array — ``{"devices": [{"mac", "ports": [{"port": N}]}]}``. Sent as
  a bare object the controller returns ``errorCode 0`` but **persists nothing**.
- Modify (``PATCH /dhcpSnoops/{id}``) takes a flat ``{mac, name, ports}`` body.
- The per-port ``OswPortSettingVO.dhcpSnoopEnable`` field is **not** the trust
  mechanism (rejected with ``-1`` on tested hardware); trust is realised here.

Dict-first: bodies are passed through unchanged. Callers build the entry shapes
(the workflow translation layer owns that); this resource only wraps create in
the mandatory ``devices`` envelope and reads/normalises for lookups.
"""

from __future__ import annotations

from typing import Any, Dict, cast

from ..mac import normalize_mac


class DhcpSnoopingResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    @staticmethod
    def _coerce_list_response(response: dict[str, Any]) -> list[dict[str, Any]]:
        result = response.get("result")
        if isinstance(result, dict):
            data = result.get("data")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        for key in ("data", "items"):
            value = response.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    def get_status(self, *, site_id: str) -> bool:
        """Return the site-wide DHCP-snooping master enable.

        GET /openapi/v1/sites/{siteId}/dhcpSnoops/status → ``result.dhcpSnoopEnable``.
        """
        response = cast(
            Dict[str, Any],
            self.client.get(self._path(f"/openapi/v1/sites/{site_id}/dhcpSnoops/status")),
        )
        result = response.get("result")
        if isinstance(result, dict):
            return bool(result.get("dhcpSnoopEnable", False))
        return False

    def set_status(self, *, site_id: str, enabled: bool) -> dict[str, Any]:
        """Enable/disable DHCP snooping site-wide.

        PATCH /openapi/v1/sites/{siteId}/dhcpSnoops/status with ``{dhcpSnoopEnable}``.
        """
        return cast(
            Dict[str, Any],
            self.client.patch(
                self._path(f"/openapi/v1/sites/{site_id}/dhcpSnoops/status"),
                json={"dhcpSnoopEnable": enabled},
            ),
        )

    def get_snoops(self, *, site_id: str) -> list[dict[str, Any]]:
        """List per-device DHCP-snooping entries for a site (``result.data``)."""
        response = self.client.get(
            self._path(f"/openapi/v1/sites/{site_id}/dhcpSnoops"),
            params={"page": 1, "pageSize": 1000},
        )
        return self._coerce_list_response(cast(Dict[str, Any], response))

    def get_supported(self, *, site_id: str) -> list[dict[str, Any]]:
        """List switches that support DHCP snooping, with their selectable ports.

        GET /openapi/v1/sites/{siteId}/switches/supportDhcpSnoop. Each device
        carries ``ports`` and ``unSelectedablePorts`` (the uplink is unselectable).
        """
        response = self.client.get(
            self._path(f"/openapi/v1/sites/{site_id}/switches/supportDhcpSnoop"),
            params={"page": 1, "pageSize": 1000},
        )
        return self._coerce_list_response(cast(Dict[str, Any], response))

    def create_snoops(self, *, site_id: str, devices: list[dict[str, Any]]) -> dict[str, Any]:
        """Create per-device snoop entries.

        POST /openapi/v1/sites/{siteId}/dhcpSnoops with the mandatory ``devices``
        envelope: ``{"devices": [{"mac": "AA-BB-…", "ports": [{"port": N}]}]}``.
        Without the wrapper the controller returns ``errorCode 0`` but persists
        nothing — so the wrapper is applied here, not left to the caller.
        """
        return cast(
            Dict[str, Any],
            self.client.post(
                self._path(f"/openapi/v1/sites/{site_id}/dhcpSnoops"),
                json={"devices": devices},
            ),
        )

    def update_snoop(self, *, site_id: str, snoop_id: str, settings: dict[str, Any]) -> dict[str, Any]:
        """Modify one existing snoop entry.

        PATCH /openapi/v1/sites/{siteId}/dhcpSnoops/{snoopId} with a flat
        ``{mac, name, ports}`` body (passed through unchanged).
        """
        return cast(
            Dict[str, Any],
            self.client.patch(
                self._path(f"/openapi/v1/sites/{site_id}/dhcpSnoops/{snoop_id}"),
                json=settings,
            ),
        )

    def delete_snoop(self, *, site_id: str, snoop_id: str) -> dict[str, Any]:
        """Delete one existing snoop entry.

        DELETE /openapi/v1/sites/{siteId}/dhcpSnoops/{snoopId}.
        """
        return cast(
            Dict[str, Any],
            self.client.delete(self._path(f"/openapi/v1/sites/{site_id}/dhcpSnoops/{snoop_id}")),
        )

    def find_snoop_by_mac(self, *, site_id: str, mac: str) -> dict[str, Any] | None:
        """Return the snoop entry whose device MAC matches ``mac``, or None.

        MAC comparison is format-insensitive (colon vs hyphen) via ``normalize_mac``.
        """
        normalized = normalize_mac(mac)
        for entry in self.get_snoops(site_id=site_id):
            candidate = entry.get("mac")
            if not isinstance(candidate, str):
                continue
            try:
                if normalize_mac(candidate) == normalized:
                    return entry
            except ValueError:
                continue
        return None
