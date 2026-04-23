"""MAC address validation and canonical formatting helpers."""

from __future__ import annotations

import macaddress  # type: ignore[import-untyped]


def normalize_mac(mac: str) -> str:
    """Validate a MAC and return Omada's canonical AA-BB-CC-DD-EE-FF form."""
    try:
        return str(macaddress.MAC(mac))
    except ValueError as exc:
        raise ValueError(
            f"Invalid MAC address '{mac}'. "
            "Use a valid EUI-48 MAC (for example: 'AA-BB-CC-DD-EE-FF', "
            "'AA:BB:CC:DD:EE:FF', or 'AABBCCDDEEFF')."
        ) from exc
