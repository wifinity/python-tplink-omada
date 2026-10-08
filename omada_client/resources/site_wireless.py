"""Site-level wireless feature settings (mesh, management-frame airtime fairness, WLAN optimization).

Panels from the controller's site wireless settings:

- **Mesh** (``/sites/{siteId}/mesh``) — the ``mesh`` block wrapping ``meshEnable``
  and its failover/DFS companions.
- **Management Frame Control** (``/sites/{siteId}/beacon-control``) — one payload
  carrying both a ``beaconControl`` block (per-band beacon/DTIM/RTS/probe fields)
  and an ``airtimeFairness`` block with per-band ``enable2g``/``enable5g``/
  ``enable6g`` flags.
- **WLAN Optimization** — Adaptive WLAN Optimization (``/sites/{siteId}/rrm/config``)
  and the Optimization Config dialog (``GET /sites/{siteId}/rfPlanning``,
  ``PUT /sites/{siteId}/rfPlanning/config``).

Both PATCH endpoints validate required fields against the whole block, so setters
here read the current object, mutate only the targeted flags, and send the merged
object back. This preserves unrelated fields and satisfies the required-field
validation without the caller supplying a full payload.
"""

from __future__ import annotations

from typing import Any, cast

_OPTIMIZATION_MODES = frozenset({0, 1})
_ADAPTIVE_MODES = {False: 0, True: 1}
_WIDTHS_5G = frozenset({20, 40, 80, 160, 240})
_WIDTHS_6G = frozenset({20, 40, 80, 160, 320})
_CUSTOM_TOGGLE_KEYS = ("channelDeployEnable", "bandDeployEnable", "channelWidthDeployEnable", "powerAdjustEnable")


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

    def get_adaptive_optimization(self, *, site_id: str) -> dict[str, Any]:
        """Return the Adaptive WLAN Optimization setting.

        GET /openapi/v1/sites/{siteId}/rrm/config → ``result`` (``mode`` 0 disabled / 1 adaptive,
        ``timeRangeEnable``, ``timeRangeAction``, ``timeRangeId``, ``resource``).
        """
        response = cast(dict[str, Any], self.client.get(self._path(f"/openapi/v1/sites/{site_id}/rrm/config")))
        return self._unwrap_result(response)

    def set_adaptive_optimization(self, *, site_id: str, enabled: bool) -> dict[str, Any]:
        """Enable or disable Adaptive WLAN Optimization, leaving the time-range fields as they are.

        Reads the current setting, sets ``mode`` (1 when ``enabled``), and PUTs the merged object
        to /openapi/v1/sites/{siteId}/rrm/config.
        """
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a bool")
        payload = self.get_adaptive_optimization(site_id=site_id)
        payload["mode"] = _ADAPTIVE_MODES[enabled]
        return cast(
            dict[str, Any],
            self.client.put(self._path(f"/openapi/v1/sites/{site_id}/rrm/config"), json=payload),
        )

    def get_optimization_config(self, *, site_id: str) -> dict[str, Any]:
        """Return the Optimization Config (the site's WLAN optimization deploy settings).

        GET /openapi/v1/sites/{siteId}/rfPlanning → ``result``: ``mode`` (0 default / 1 custom),
        the four deploy toggles at the top level, and, in custom mode, an ``advancedSetting`` block.
        The controller serves this config only by GET on ``rfPlanning``; ``rfPlanning/config``
        answers PUT only.
        """
        response = cast(dict[str, Any], self.client.get(self._path(f"/openapi/v1/sites/{site_id}/rfPlanning")))
        return self._unwrap_result(response)

    @staticmethod
    def custom_setting_from_config(config: dict[str, Any]) -> dict[str, Any]:
        """Project a :meth:`get_optimization_config` result onto the PUT ``customSetting`` shape."""
        custom: dict[str, Any] = {key: config[key] for key in _CUSTOM_TOGGLE_KEYS if key in config}
        advanced = config.get("advancedSetting")
        if isinstance(advanced, dict):
            custom["advancedSetting"] = advanced
        return custom

    @staticmethod
    def _validate_width_range(width_range: Any) -> None:
        if not isinstance(width_range, dict):
            raise ValueError("advancedSetting.widthRange must be a dict")
        for band, allowed in (("5g", _WIDTHS_5G), ("6g", _WIDTHS_6G)):
            low, high = width_range.get(f"minWidth{band}"), width_range.get(f"maxWidth{band}")
            if low is None and high is None:
                continue
            if low not in allowed or high not in allowed:
                raise ValueError(f"{band} channel width range must use widths from {sorted(allowed)}; got {low}-{high}")
            if low > high:
                raise ValueError(f"{band} channel width range minimum {low} exceeds maximum {high}")

    def set_optimization_config(
        self,
        *,
        site_id: str,
        mode: int,
        custom_setting: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Set the Optimization Config.

        ``mode`` 0 selects the controller's default optimization and takes no ``custom_setting``.
        ``mode`` 1 selects custom optimization and requires ``custom_setting``: the four deploy
        toggles (``channelDeployEnable``, ``bandDeployEnable``, ``channelWidthDeployEnable``,
        ``powerAdjustEnable``) and an ``advancedSetting`` block (``widthSelectEn`` with
        ``widthRange``, ``powerMode``, ``powerThreshold``, ``exclude5gChEn``, ``exclude5gCh``).
        Build ``custom_setting`` from the current config with :meth:`custom_setting_from_config`
        to change one field and keep the rest. PUTs /openapi/v1/sites/{siteId}/rfPlanning/config.
        """
        if isinstance(mode, bool) or mode not in _OPTIMIZATION_MODES:
            raise ValueError(f"mode must be one of {sorted(_OPTIMIZATION_MODES)}; got {mode!r}")
        payload: dict[str, Any] = {"mode": mode}
        if mode == 0:
            if custom_setting is not None:
                raise ValueError("custom_setting is only valid with mode=1")
        else:
            if not isinstance(custom_setting, dict) or not custom_setting:
                raise ValueError("custom_setting must be a non-empty dict when mode=1")
            advanced = custom_setting.get("advancedSetting")
            if isinstance(advanced, dict) and "widthRange" in advanced:
                self._validate_width_range(advanced["widthRange"])
            payload["customSetting"] = custom_setting
        return cast(
            dict[str, Any],
            self.client.put(self._path(f"/openapi/v1/sites/{site_id}/rfPlanning/config"), json=payload),
        )
