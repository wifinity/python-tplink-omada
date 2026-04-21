"""Fetch upstream Omada OpenAPI spec."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_SPEC_URL = "https://use1-omada-northbound.tplinkcloud.com/v3/api-docs/00%20All"
RAW_SPEC_PATH = Path("spec/raw/all.json")


def main() -> None:
    source_url = os.getenv("OMADA_OPENAPI_URL", DEFAULT_SPEC_URL)
    request = Request(source_url, headers={"User-Agent": "python-tplink-omada/0.1.0"})
    with urlopen(request, timeout=60) as response:  # nosec B310 - fixed trusted endpoint
        payload = json.loads(response.read().decode("utf-8"))

    RAW_SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_SPEC_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Fetched spec from {source_url} -> {RAW_SPEC_PATH}")


if __name__ == "__main__":
    main()
