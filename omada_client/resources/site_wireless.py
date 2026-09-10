"""Site-level wireless feature settings (mesh, management-frame airtime fairness).

Two panels from the controller's site wireless settings:

- **Mesh** (``/sites/{siteId}/mesh``) — the ``mesh`` block wrapping ``meshEnable``
  and its failover/DFS companions.
- **Management Frame Control** (``/sites/{siteId}/beacon-control``) — one payload
  carrying both a ``beaconControl`` block (per-band beacon/DTIM/RTS/probe fields)
  and an ``airtimeFairness`` block with per-band ``enable2g``/``enable5g``/
  ``enable6g`` flags.

Both PATCH endpoints validate required fields against the whole block, so setters
here read the current object, mutate only the targeted flags, and send the merged
object back. This preserves unrelated fields and satisfies the required-field
validation without the caller supplying a full payload.
"""

from __future__ import annotations

from typing import Any, cast


class SiteWirelessResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    @staticmethod
    def _unwrap_result(response: dict[str, Any]) -> dict[str, Any]:
        result = response.get("result")
        if isinstance(result, dict):
            return result
        return {}

    def get_mesh(self, *, site_id: str) -> dict[str, Any]:
        """Return the site ``mesh`` block.

        GET /openapi/v1/sites/{siteId}/mesh → ``result.mesh`` (``meshEnable``,
        ``autoFailoverEnable``, ``defGatewayEnable``, ``fullSector``, ``gateway``).
        """
        response = cast(dict[str, Any], self.client.get(self._path(f"/openapi/v1/sites/{site_id}/mesh")))
        mesh = self._unwrap_result(response).get("mesh")
        return mesh if isinstance(mesh, dict) else {}

    def set_mesh(self, *, site_id: str, enabled: bool) -> dict[str, Any]:
        """Set the site mesh master enable.

        Reads the current ``mesh`` block, sets ``meshEnable`` to ``enabled``, and
        PATCHes /openapi/v1/sites/{siteId}/mesh with the merged ``{"mesh": {...}}``.
        """
        mesh = self.get_mesh(site_id=site_id)
        mesh["meshEnable"] = enabled
        return cast(
            dict[str, Any],
            self.client.patch(self._path(f"/openapi/v1/sites/{site_id}/mesh"), json={"mesh": mesh}),
        )

    def get_beacon_control(self, *, site_id: str) -> dict[str, Any]:
        """Return the Management Frame Control payload.

        GET /openapi/v1/sites/{siteId}/beacon-control → ``result`` with both the
        ``beaconControl`` and ``airtimeFairness`` blocks.
        """
        response = cast(dict[str, Any], self.client.get(self._path(f"/openapi/v1/sites/{site_id}/beacon-control")))
        return self._unwrap_result(response)

    def get_airtime_fairness(self, *, site_id: str) -> dict[str, Any]:
        """Return the per-band airtime fairness flags (``enable2g``/``enable5g``/``enable6g``)."""
        airtime = self.get_beacon_control(site_id=site_id).get("airtimeFairness")
        return airtime if isinstance(airtime, dict) else {}

    def set_airtime_fairness(
        self,
        *,
        site_id: str,
        enable_2g: bool,
        enable_5g: bool,
        enable_6g: bool,
    ) -> dict[str, Any]:
        """Set airtime fairness per band.

        Reads the current Management Frame Control payload, replaces the
        ``airtimeFairness`` flags, and PATCHes /openapi/v1/sites/{siteId}/beacon-control
        with the merged body — keeping the ``beaconControl`` block intact so its
        required per-band fields stay satisfied.
        """
        payload = self.get_beacon_control(site_id=site_id)
        payload["airtimeFairness"] = {
            "enable2g": enable_2g,
            "enable5g": enable_5g,
            "enable6g": enable_6g,
        }
        return cast(
            dict[str, Any],
            self.client.patch(self._path(f"/openapi/v1/sites/{site_id}/beacon-control"), json=payload),
        )
