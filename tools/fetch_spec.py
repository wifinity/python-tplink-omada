"""Fetch the Omada OpenAPI spec and stamp a controller-version manifest.

The Omada Open API is effectively unversioned (``info.version`` is ``v0.1`` on
both the TP-Link cloud spec and a controller's own ``/v3/api-docs``), so the
baseline is anchored to the controller triple read from ``/api/info``
(``controllerVer`` / ``apiVer``) plus the fetch date, written to a manifest
alongside the raw spec.

Source selection:

* ``--base-url URL`` (or ``OMADA_BASE_URL``): fetch from a local controller;
  the spec comes from ``{base}/v3/api-docs/00%20All`` and the version manifest
  from ``{base}/api/info``.
* ``--url URL`` (or ``OMADA_OPENAPI_URL``): explicit spec URL override.
* neither: the public TP-Link cloud spec (unchanged default behaviour). The
  cloud has no ``/api/info``, so the manifest records null controller versions.

The manifest never records the source host/IP — only a ``source`` kind
(``controller`` / ``cloud``) — so a private controller address is not committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DEFAULT_SPEC_URL = "https://use1-omada-northbound.tplinkcloud.com/v3/api-docs/00%20All"
SPEC_PATH_SUFFIX = "/v3/api-docs/00%20All"
INFO_PATH = "/api/info"
USER_AGENT = "python-tplink-omada/0.1.0"

# A controller serves its own base URL in the spec's `servers` block; overwrite it
# with a host-agnostic placeholder so a private controller address is never committed
# and the baseline is identical regardless of which controller produced it. The SDK
# supplies the real base_url at runtime and does not use this block.
SERVER_PLACEHOLDER = {
    "url": "https://omada-controller.example",
    "description": "Host-agnostic placeholder; base URL is supplied at runtime.",
}

RAW_SPEC_PATH = Path("spec/raw/all.json")
MANIFEST_PATH = Path("spec/raw/manifest.json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch the Omada OpenAPI spec and stamp a version manifest.")
    parser.add_argument("--base-url", help="Controller base URL; spec + /api/info are derived from it.")
    parser.add_argument("--url", help="Explicit spec URL override (no /api/info derivation for the cloud host).")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification (self-signed controllers).")
    return parser.parse_args(argv)


def _normalize_base(base_url: str) -> str:
    resolved = base_url.rstrip("/")
    if not resolved:
        raise ValueError("base_url is required")
    return resolved


def resolve_sources(args: argparse.Namespace, env: Mapping[str, str]) -> tuple[str, str | None, str]:
    """Return ``(spec_url, info_url_or_none, source_kind)``.

    ``info_url`` is only set for a controller source; the cloud spec has no
    ``/api/info`` endpoint.
    """
    base = args.base_url or env.get("OMADA_BASE_URL")
    explicit_url = args.url or env.get("OMADA_OPENAPI_URL")
    cloud_host = urlparse(DEFAULT_SPEC_URL).netloc

    if base:
        api_base: str | None = _normalize_base(base)
        spec_url = f"{api_base}{SPEC_PATH_SUFFIX}"
    elif explicit_url:
        spec_url = explicit_url
        parsed = urlparse(explicit_url)
        api_base = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else None
    else:
        spec_url = DEFAULT_SPEC_URL
        api_base = None

    source = "cloud" if urlparse(spec_url).netloc == cloud_host else "controller"
    info_url = f"{api_base}{INFO_PATH}" if (api_base and source == "controller") else None
    return spec_url, info_url, source


def resolve_verify(args: argparse.Namespace, env: Mapping[str, str]) -> bool:
    if args.insecure:
        return False
    value = env.get("OMADA_VERIFY")
    if value is not None:
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return True


def _load_url(url: str, *, verify: bool = True) -> bytes:
    context = None if verify else ssl._create_unverified_context()
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(
        request, timeout=60, context=context
    ) as response:  # nosec B310 - configurable controller/cloud endpoint
        return response.read()


def fetch_json(url: str, *, verify: bool = True) -> dict:
    return json.loads(_load_url(url, verify=verify).decode("utf-8"))


def sanitize_spec(spec: dict) -> dict:
    """Replace the `servers` block so no source host/IP is written to the raw spec."""
    if "servers" in spec:
        spec["servers"] = [dict(SERVER_PLACEHOLDER)]
    return spec


def build_manifest(
    info: dict | None, *, source: str, spec_info_version: str | None, spec_sha256: str, fetched_at: str
) -> dict:
    # /api/info wraps the payload under "result"; tolerate a flat shape too.
    payload = (info or {}).get("result", info) or {}
    return {
        "source": source,
        "controllerVer": payload.get("controllerVer"),
        "apiVer": payload.get("apiVer"),
        "spec_info_version": spec_info_version,
        "spec_sha256": spec_sha256,
        "fetched_at": fetched_at,
    }


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    spec_url, info_url, source = resolve_sources(args, os.environ)
    verify = resolve_verify(args, os.environ)

    spec_payload = sanitize_spec(fetch_json(spec_url, verify=verify))
    raw_bytes = (json.dumps(spec_payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    RAW_SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_SPEC_PATH.write_bytes(raw_bytes)

    info = fetch_json(info_url, verify=verify) if info_url else {}
    spec_info_version = (spec_payload.get("info") or {}).get("version")
    manifest = build_manifest(
        info,
        source=source,
        spec_info_version=spec_info_version,
        spec_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Fetched spec from {source} -> {RAW_SPEC_PATH}")
    print(f"Wrote manifest -> {MANIFEST_PATH} (controllerVer={manifest['controllerVer']}, apiVer={manifest['apiVer']})")


if __name__ == "__main__":
    main()
