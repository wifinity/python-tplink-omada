"""Switch global (system) 802.1X settings for an Omada site.

Omada scopes switch 802.1X as a single **per-site** resource
(``/openapi/v1/{omadacId}/sites/{siteId}/dot1x``), not per switch:

- ``GET`` returns the current ``Dot1xSwitchResOpenApiVO`` (system ``enable``,
  auth method, ``radiusProfileId``, ``nasId``, …). It does **not** echo the
  per-port ``switches`` array.
- ``PATCH`` takes a ``Dot1xSwitchOpenApiVO`` body. The controller requires
  ``authMode`` (0: PAP, 1: EAP), ``authType`` (0: port-based, 1: mac-based),
  ``enable``, ``mab``, ``macFormat``, ``radiusProfileId`` and ``vlanAssign``.
  Optional: ``guestVlan``, ``nasId`` and ``switches`` — the latter being the
  per-port enablement (``dot1xPorts`` / ``mabPorts`` keyed by switch ``mac``).

The RADIUS profile is referenced by ``radiusProfileId``; resolve a profile name
to its id via ``RadiusProfilesResource.get``. Dict-first: the body is passed
through unchanged, so the workflow layer owns building and reconciling it
(read-modify-write, so unmanaged required fields and the per-port ``switches``
array are preserved).
"""

from __future__ import annotations

from typing import Any, cast


class SwitchDot1xResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    def get(self, *, site_id: str) -> dict[str, Any]:
        """Return the site's switch 802.1X setting (``result`` unwrapped).

        GET /openapi/v1/sites/{siteId}/dot1x → ``Dot1xSwitchResOpenApiVO``.
        Returns an empty dict when the controller reports no ``result`` (e.g. a
        switch that has never had 802.1X configured).
        """
        response = cast(
            dict[str, Any],
            self.client.get(self._path(f"/openapi/v1/sites/{site_id}/dot1x")),
        )
        result = response.get("result")
        if isinstance(result, dict):
            return result
        return {}

    def update(self, *, site_id: str, settings: dict[str, Any]) -> dict[str, Any]:
        """Update the site's switch 802.1X setting.

        PATCH /openapi/v1/sites/{siteId}/dot1x with a ``Dot1xSwitchOpenApiVO``
        body (passed through unchanged). Required keys: ``authMode``,
        ``authType``, ``enable``, ``mab``, ``macFormat``, ``radiusProfileId`` and
        ``vlanAssign``.
        """
        return cast(
            dict[str, Any],
            self.client.patch(
                self._path(f"/openapi/v1/sites/{site_id}/dot1x"),
                json=settings,
            ),
        )
