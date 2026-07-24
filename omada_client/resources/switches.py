"""Switch operations implemented as a typed facade over devices."""

from __future__ import annotations

from typing import Any, cast

from ..exceptions import DeviceNotFoundError
from ..mac import normalize_mac
from .devices import augment_device_status_meanings


class SwitchesResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def all(
        self,
        *,
        site_id: str,
        page: int = 1,
        page_size: int = 1000,
        **params: Any,
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            self.client.devices.all(
                site_id=site_id,
                page=page,
                page_size=page_size,
                deviceType="switch",
                **params,
            ),
        )

    def get_by_mac(self, *, site_id: str, mac: str) -> dict[str, Any]:
        normalized_mac = normalize_mac(mac)
        response = cast(
            dict[str, Any],
            self.client.devices.all(site_id=site_id, searchKey=normalized_mac, deviceType="switch"),
        )
        items = self._extract_items(response)
        for item in items:
            if not isinstance(item, dict):
                continue
            if self._matches_mac(item.get("mac"), normalized_mac):
                matched = cast(dict[str, Any], item)
                augment_device_status_meanings(matched)
                return matched
        raise DeviceNotFoundError(f"Switch with MAC '{mac}' not found in site '{site_id}'")

    def get_by_name(self, *, site_id: str, name: str) -> dict[str, Any]:
        response = cast(
            dict[str, Any],
            self.client.devices.all(site_id=site_id, searchKey=name, deviceType="switch"),
        )
        items = self._extract_items(response)
        exact_matches: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("name") == name:
                matched = cast(dict[str, Any], item)
                augment_device_status_meanings(matched)
                exact_matches.append(matched)
        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(exact_matches) > 1:
            raise ValueError(f"Multiple switches named '{name}' found in site '{site_id}'")
        raise ValueError(f"Switch named '{name}' not found in site '{site_id}'")

    def create(
        self,
        *,
        site_id: str,
        device_key: str,
        name: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            self.client.devices.add_by_device_key(
                site_id=site_id,
                device_key=device_key,
                name=name,
                username=username,
                password=password,
            ),
        )

    def start_adopt(
        self,
        *,
        site_id: str,
        mac: str,
        username: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            self.client.devices.start_adopt(site_id=site_id, mac=mac, username=username, password=password),
        )

    def check_adopt(self, *, site_id: str, mac: str) -> dict[str, Any]:
        return cast(dict[str, Any], self.client.devices.check_adopt(site_id=site_id, mac=mac))

    def get_ports(self, *, site_id: str, switch_mac: str) -> list[dict[str, Any]]:
        """Return current port settings for one switch.

        Uses POST /switches/ports/select with selectAll=true filtered to this switch MAC.
        Each item in the returned list is an OswPortVO with fields including
        'port' (int), 'name' (str), and 'disable' (bool).
        Returns [] when the switch is not present in the response.
        """
        normalized = normalize_mac(switch_mac)
        response = cast(
            dict[str, Any],
            self.client.post(
                self.client.api_path(f"/openapi/v1/sites/{site_id}/switches/ports/select"),
                json={"selectAll": True, "switchList": [], "filters": {"switchMac": normalized}},
            ),
        )
        all_switches = self._extract_items(response)
        for sw in all_switches:
            if not isinstance(sw, dict):
                continue
            if self._matches_mac(sw.get("mac"), normalized):
                ports = sw.get("ports") or []
                return list(ports) if isinstance(ports, list) else []
        return []

    def set_ports_name(
        self,
        *,
        site_id: str,
        switch_mac: str,
        port_names: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Rename multiple ports in one request.

        port_names: list of {port: int, name: str}
        PUT /switches/{switchMac}/multi-ports/name
        """
        normalized = normalize_mac(switch_mac)
        return cast(
            dict[str, Any],
            self.client.put(
                self.client.api_path(f"/openapi/v1/sites/{site_id}/switches/{normalized}/multi-ports/name"),
                json={"portNameList": port_names},
            ),
        )

    def get_lldp_neighbors(self, *, site_id: str, switch_mac: str) -> list[dict[str, Any]]:
        """Return LLDP neighbor entries for one switch.

        Uses GET /openapi/v1/sites/{siteId}/switches/{switchMac}/lldp-neighbors.
        Each item in the returned list is an OswLldpNeighborVO with fields
        including 'portId' (int), 'deviceId' (str, MAC-like chassis id when
        present), 'systemName', 'neighborPortId', 'ttl', and 'capabilities'.
        Returns [] when the switch has no neighbors, is not yet adopted, or the
        MAC is unrecognized — the controller does not distinguish these cases.
        """
        normalized = normalize_mac(switch_mac)
        response = cast(
            dict[str, Any],
            self.client.get(
                self.client.api_path(f"/openapi/v1/sites/{site_id}/switches/{normalized}/lldp-neighbors"),
                params={"page": 1, "pageSize": 1000},
            ),
        )
        return cast(list[dict[str, Any]], self._extract_items(response))

    def get_port_profiles(self, *, site_id: str) -> list[dict[str, Any]]:
        """Return all LAN port profiles for the site.

        Calls GET /openapi/v2/.../sites/{siteId}/lan-profiles.
        """
        url = self.client.api_path(f"/openapi/v2/sites/{site_id}/lan-profiles")
        response = cast(dict[str, Any], self.client.get(url, params={"page": 1, "pageSize": 1000}))
        return cast(list[Any], self._extract_items(response))

    def set_port_profiles(
        self,
        *,
        site_id: str,
        switch_mac: str,
        port_list: list[int],
        profile_name: str,
    ) -> None:
        """Set a named port profile on each port in port_list.

        Resolves the profile name to an ID via get_port_profiles, then calls
        PUT /switches/{switchMac}/ports/{port}/profile for each port.
        """
        profiles = self.get_port_profiles(site_id=site_id)
        profile_id = next(
            (p["id"] for p in profiles if isinstance(p, dict) and p.get("name") == profile_name),
            None,
        )
        if profile_id is None:
            raise ValueError(f"Port profile '{profile_name}' not found in site '{site_id}'")
        normalized = normalize_mac(switch_mac)
        for port in port_list:
            self.client.put(
                self.client.api_path(f"/openapi/v1/sites/{site_id}/switches/{normalized}/ports/{port}/profile"),
                json={"profileId": profile_id},
            )

    def update_switch_port(
        self,
        *,
        site_id: str,
        switch_mac: str,
        port: int,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply per-port config to one switch port.

        PATCH /switches/{switchMac}/ports/{port} with ``settings`` as the
        ``OswPortSettingVO`` body. The body is passed through verbatim, dict-first:
        this method does not validate, translate, or default any field.

        ``OswPortSettingVO`` is the per-port *override* model. Its fields (VLAN
        intent ``nativeNetworkId``/``nativeBridgeVlan``/``tagNetworkIds``/
        ``untagNetworkIds``/``networkTagsSetting``, ``dhcpSnoopEnable``, ``name``,
        and port-config keys such as ``poe``/``dot1x``/``stormCtrl``) take effect only
        when ``profileOverrideEnable`` is true; otherwise the port inherits from its
        assigned profile. VLAN fields take Omada LAN network IDs (strings), not raw
        VLAN numbers — the caller resolves those (e.g. via
        ``client.lan_networks.vlan_id_to_network_id``).

        Admin enable/disable is managed via the port profile (see
        ``set_port_profiles``), not the ``disable`` field here.

        Single-port only; callers loop per port and do their own read-before-write
        diff. Returns the raw controller response (``OperationResponseString``).
        """
        normalized = normalize_mac(switch_mac)
        return cast(
            dict[str, Any],
            self.client.patch(
                self.client.api_path(f"/openapi/v1/sites/{site_id}/switches/{normalized}/ports/{port}"),
                json=settings,
            ),
        )

    def update_loopback_control(
        self,
        *,
        site_id: str,
        switch_mac: str,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply device-tier STP / loopback control to one switch.

        PUT /switches/{switchMac}/config/loopback with ``settings`` as the
        ``SwitchLoopbackControl`` body. The body is passed through verbatim,
        dict-first: this method does not validate, translate, or default any
        field. Its fields include:

        - ``stp`` — spanning-tree mode: ``0`` OFF, ``1`` STP, ``2`` RSTP, ``3`` MSTP.
        - ``priority`` — device-wide bridge priority: an integer 0..61440 divisible
          by 4096 (the STP root-bridge election weight). This is the only bridge
          priority in the Omada model that is genuinely device-global; the
          per-port/per-profile ``spanningTreeSetting.priority`` is unrelated.
        - ``mstp`` (``OswStpMstpConfigOpenApiVO``) plus timer knobs
          ``forwardDelay`` / ``helloTime`` / ``maxAge`` / ``maxHops`` /
          ``txHoldCount`` and ``loopbackDetectEnable``.

        The endpoint is PUT-only (there is no GET twin), so it sets absolute state
        and is naturally idempotent; the caller does not read-before-write here.
        Note: DHCP snooping is unrelated to this endpoint — it has a dedicated
        site-wide enable and per-device snoop entries; see ``DhcpSnoopingResource``
        (``client.dhcp_snooping``). The per-port ``OswPortSettingVO.dhcpSnoopEnable``
        field is not the trust mechanism.

        Single-switch only. Returns the raw controller response
        (``OperationResponseWithoutResult``).
        """
        normalized = normalize_mac(switch_mac)
        return cast(
            dict[str, Any],
            self.client.put(
                self.client.api_path(f"/openapi/v1/sites/{site_id}/switches/{normalized}/config/loopback"),
                json=settings,
            ),
        )

    def create_port_profile(self, *, site_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        """Create a LAN port profile from a dict-first profile body.

        POST /openapi/v2/.../sites/{siteId}/lan-profiles with the profile body
        (a LanProfileSettingOpenApiVO) passed through unchanged — no validation
        or value translation happens here. Returns the created identity from
        ResponseIdVO ({"id": "<newProfileId>"}).
        """
        url = self.client.api_path(f"/openapi/v2/sites/{site_id}/lan-profiles")
        response = cast(dict[str, Any], self.client.post(url, json=profile))
        result = response.get("result")
        if isinstance(result, dict):
            return cast(dict[str, Any], result)
        return response

    def update_port_profile(
        self,
        *,
        site_id: str,
        profile: dict[str, Any],
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        """Update a LAN port profile with a dict-first profile body.

        When ``profile_id`` is omitted the id is resolved from ``profile['name']``.
        PATCH /openapi/v2/.../sites/{siteId}/lan-profiles/{profileId} with the
        profile body passed through unchanged.
        """
        if profile_id is None:
            profile_id = self._resolve_port_profile_id_by_name(site_id=site_id, name=profile.get("name"))
        url = self.client.api_path(f"/openapi/v2/sites/{site_id}/lan-profiles/{profile_id}")
        return cast(dict[str, Any], self.client.patch(url, json=profile))

    def delete_port_profile(
        self,
        *,
        site_id: str,
        profile_id: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Delete a LAN port profile.

        Exactly one of ``profile_id`` or ``name`` must be supplied; ``name`` is
        resolved to an id via get_port_profiles.
        """
        if (profile_id is None) == (name is None):
            raise ValueError("Provide exactly one of 'profile_id' or 'name'")
        if profile_id is None:
            profile_id = self._resolve_port_profile_id_by_name(site_id=site_id, name=name)
        url = self.client.api_path(f"/openapi/v2/sites/{site_id}/lan-profiles/{profile_id}")
        return cast(dict[str, Any], self.client.delete(url))

    def upsert_port_profile(self, *, site_id: str, profile: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Create-or-update a LAN port profile by name.

        Returns ``(profile_dict, created)``. Resolves ``profile['name']`` against
        the existing profiles: if a match exists it is PATCHed and returned with
        ``created=False``; otherwise a new profile is POSTed and returned with
        ``created=True``.

        Pure create-vs-update dispatch — no diffing, no value translation, no
        naming policy. Unlike RadiusProfilesResource.upsert (which
        is create-if-absent only), this updates on conflict.
        """
        name = profile.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("profile must include a non-empty 'name'")
        match = next(
            (p for p in self.get_port_profiles(site_id=site_id) if isinstance(p, dict) and p.get("name") == name),
            None,
        )
        if match is not None:
            self.update_port_profile(site_id=site_id, profile_id=match["id"], profile=profile)
            return match, False
        created = self.create_port_profile(site_id=site_id, profile=profile)
        return created, True

    def _resolve_port_profile_id_by_name(self, *, site_id: str, name: Any) -> str:
        if not isinstance(name, str) or not name:
            raise ValueError("name must be a non-empty string")
        matches = [p for p in self.get_port_profiles(site_id=site_id) if isinstance(p, dict) and p.get("name") == name]
        if not matches:
            raise ValueError(f"Port profile '{name}' not found in site '{site_id}'")
        if len(matches) > 1:
            raise ValueError(f"Multiple port profiles named '{name}' found in site '{site_id}'")
        profile_id = matches[0].get("id")
        if not isinstance(profile_id, str) or not profile_id:
            raise ValueError(f"Port profile '{name}' does not include a valid id")
        return profile_id

    def delete(self, *, site_id: str, mac: str) -> dict[str, Any]:
        normalized_mac = normalize_mac(mac)
        return cast(dict[str, Any], self.client.devices.delete(site_id=site_id, mac=normalized_mac))

    @staticmethod
    def _extract_items(response: dict[str, Any]) -> list[Any]:
        for key in ("data", "result", "items", "list"):
            value = response.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                for nested_key in ("data", "items", "list"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, list):
                        return nested_value
        return []

    @staticmethod
    def _matches_mac(value: Any, normalized_mac: str) -> bool:
        if not isinstance(value, str):
            return False
        try:
            return normalize_mac(value) == normalized_mac
        except ValueError:
            return False
