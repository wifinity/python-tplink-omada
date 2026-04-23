from __future__ import annotations

import pytest

from omada_client.mac import normalize_mac


@pytest.mark.parametrize(
    "raw_mac",
    [
        "aa:bb:cc:dd:ee:ff",
        "AA-BB-CC-DD-EE-FF",
        "aabbccddeeff",
        "aabb.ccdd.eeff",
    ],
)
def test_normalize_mac_accepts_supported_formats(raw_mac: str) -> None:
    assert normalize_mac(raw_mac) == "AA-BB-CC-DD-EE-FF"


def test_normalize_mac_rejects_invalid_mac() -> None:
    with pytest.raises(ValueError, match="Invalid MAC address"):
        normalize_mac("not-a-mac")
