"""LAN network (VLAN) operations for an Omada site.

LAN networks are Omada's representation of 802.1Q VLANs.  Each named LAN
network corresponds to one VLAN ID; the controller assigns a string Network ID
that other API resources (port profiles, port overrides) reference.

Idempotency key: VLAN ID integer (``vlan`` field).  The ``vlan_id_to_network_id``
helper provides a one-shot lookup dict for callers that need to resolve VLAN
integers to Omada network IDs (e.g. the port-config workflow).

DHCP server:
    The controller may enable a DHCP server on newly created networks.
    Callers that need the DHCP server off must pass ``dhcp_server_enabled=False``
    to ``create()`` (the default) and check the live value during updates.  The
    ``upsert_site_vlans`` workflow activity owns enforcement of this convention.
"""

from __future__ import annotations

from typing import Any, Dict, cast


class LanNetworksResource:
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

        for key in ("data", "items", "result"):
            value = response.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    def all(self, *, site_id: str) -> list[dict[str, Any]]:
        """List all LAN networks for a site."""
        response = self.client.get(
            self._path(f"/openapi/v1/sites/{site_id}/lan-networks"),
            params={"page": 1, "pageSize": 1000},
        )
        return self._coerce_list_response(cast(Dict[str, Any], response))

    def get(
        self,
        *,
        site_id: str,
        network_id: str | None = None,
        vlan_id: int | None = None,
    ) -> dict[str, Any]:
        """Resolve a LAN network by Omada network ID string or VLAN integer.

        Exactly one of ``network_id`` or ``vlan_id`` must be supplied.
        Raises ``LanNetworkNotFoundError`` when no match is found.
        """
        from ..exceptions import LanNetworkNotFoundError

        if (network_id is None) == (vlan_id is None):
            raise ValueError("Provide exactly one of 'network_id' or 'vlan_id'")

        if network_id is not None:
            response = self.client.get(
                self._path(f"/openapi/v1/sites/{site_id}/lan-networks/{network_id}"),
            )
            result = cast(Dict[str, Any], response).get("result")
            if isinstance(result, dict):
                return result
            raise LanNetworkNotFoundError(f"LAN network {network_id!r} not found on site {site_id!r}")

        # vlan_id lookup — scan the list
        for net in self.all(site_id=site_id):
            if net.get("vlan") == vlan_id:
                return net
        raise LanNetworkNotFoundError(f"LAN network with VLAN {vlan_id} not found on site {site_id!r}")

    def create(
        self,
        *,
        site_id: str,
        name: str,
        vlan_id: int,
        dhcp_server_enabled: bool = False,
    ) -> dict[str, Any]:
        """Create a VLAN-type LAN network.

        ``dhcp_server_enabled`` defaults to ``False``.  Pass ``True`` only when
        the controller's DHCP server is explicitly wanted on this segment.
        """
        if not isinstance(name, str) or not name:
            raise ValueError("name must be a non-empty string")
        payload: dict[str, Any] = {
            "name": name,
            "purpose": 0,
            "vlan": vlan_id,
            "igmpSnoopEnable": False,
            "dhcpSettingsVO": {"enable": dhcp_server_enabled},
        }
        response = self.client.post(
            self._path(f"/openapi/v1/sites/{site_id}/lan-networks"),
            json=payload,
        )
        return cast(Dict[str, Any], response)

    def update(
        self,
        *,
        site_id: str,
        network_id: str | None = None,
        vlan_id: int | None = None,
        name: str | None = None,
        dhcp_server_enabled: bool | None = None,
    ) -> dict[str, Any]:
        """Update a VLAN-type LAN network.

        Exactly one of ``network_id`` or ``vlan_id`` must be supplied.
        Fetches the current network state and merges the supplied changes before
        PATCHing back, so callers only need to supply the fields they want to
        change.  The API requires the full object on PATCH.
        """
        if (network_id is None) == (vlan_id is None):
            raise ValueError("Provide exactly one of 'network_id' or 'vlan_id'")
        existing = self.get(site_id=site_id, network_id=network_id, vlan_id=vlan_id)
        resolved_network_id = existing["id"]
        payload = dict(existing)
        if name is not None:
            payload["name"] = name
        if dhcp_server_enabled is not None:
            dhcp = dict(payload.get("dhcpSettingsVO") or {})
            dhcp["enable"] = dhcp_server_enabled
            payload["dhcpSettingsVO"] = dhcp
        response = self.client.patch(
            self._path(f"/openapi/v1/sites/{site_id}/lan-networks/{resolved_network_id}"),
            json=payload,
        )
        return cast(Dict[str, Any], response)

    def delete(
        self,
        *,
        site_id: str,
        network_id: str | None = None,
        vlan_id: int | None = None,
    ) -> dict[str, Any]:
        """Delete a LAN network.

        Exactly one of ``network_id`` or ``vlan_id`` must be supplied.
        When ``vlan_id`` is given the network ID is resolved via ``get()``.
        """
        if (network_id is None) == (vlan_id is None):
            raise ValueError("Provide exactly one of 'network_id' or 'vlan_id'")
        if network_id is None:
            existing = self.get(site_id=site_id, vlan_id=vlan_id)
            network_id = existing["id"]
        response = self.client.delete(
            self._path(f"/openapi/v1/sites/{site_id}/lan-networks/{network_id}"),
        )
        return cast(Dict[str, Any], response)

    def vlan_id_to_network_id(self, *, site_id: str) -> dict[int, str]:
        """Return ``{vlan_id: network_id}`` for all LAN networks on a site.

        Intended for callers that need to translate VLAN integers to Omada
        network ID strings (e.g. port-profile or port-override configuration).
        Call once per site per workflow run and cache the result locally.
        """
        result: dict[int, str] = {}
        for net in self.all(site_id=site_id):
            vid = net.get("vlan")
            nid = net.get("id")
            if isinstance(vid, int) and isinstance(nid, str) and nid:
                result[vid] = nid
        return result
