from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import fetch_spec

SPEC_PAYLOAD = {
    "openapi": "3.0.1",
    "info": {"title": "Omada Open API", "version": "v0.1"},
    "servers": [{"url": "https://192.0.2.10:8043", "description": "Generated server url"}],
    "paths": {},
}
INFO_PAYLOAD = {
    "errorCode": 0,
    "result": {"controllerVer": "5.15.20.18", "apiVer": "3", "omadacId": "secret-omadac"},
}


def _fake_loader(calls: list[str]):
    """Return a stub for fetch_spec._load_url that records URLs and serves canned JSON."""

    def _load(url: str, *, verify: bool = True) -> bytes:
        calls.append(url)
        if url.endswith(fetch_spec.INFO_PATH):
            return json.dumps(INFO_PAYLOAD).encode("utf-8")
        return json.dumps(SPEC_PAYLOAD).encode("utf-8")

    return _load


def _redirect_outputs(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    raw = tmp_path / "raw" / "all.json"
    manifest = tmp_path / "raw" / "manifest.json"
    monkeypatch.setattr(fetch_spec, "RAW_SPEC_PATH", raw)
    monkeypatch.setattr(fetch_spec, "MANIFEST_PATH", manifest)
    return raw, manifest


def test_controller_source_writes_spec_and_version_manifest(tmp_path: Path, monkeypatch) -> None:
    raw, manifest_path = _redirect_outputs(tmp_path, monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(fetch_spec, "_load_url", _fake_loader(calls))

    fetch_spec.main(["--base-url", "https://fake-controller", "--insecure"])

    written = json.loads(raw.read_text(encoding="utf-8"))
    # servers block is sanitized to the host-agnostic placeholder; everything else is verbatim
    assert written["servers"] == [fetch_spec.SERVER_PLACEHOLDER]
    assert {k: v for k, v in written.items() if k != "servers"} == {
        k: v for k, v in SPEC_PAYLOAD.items() if k != "servers"
    }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source"] == "controller"
    assert manifest["controllerVer"] == "5.15.20.18"
    assert manifest["apiVer"] == "3"
    assert manifest["spec_info_version"] == "v0.1"
    assert len(manifest["spec_sha256"]) == 64
    assert manifest["fetched_at"].endswith("Z")
    # both the spec and /api/info were fetched
    assert any(u.endswith(fetch_spec.SPEC_PATH_SUFFIX) for u in calls)
    assert any(u.endswith(fetch_spec.INFO_PATH) for u in calls)


def test_cloud_default_skips_api_info(tmp_path: Path, monkeypatch) -> None:
    _, manifest_path = _redirect_outputs(tmp_path, monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(fetch_spec, "_load_url", _fake_loader(calls))

    fetch_spec.main([])

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source"] == "cloud"
    assert manifest["controllerVer"] is None
    assert manifest["apiVer"] is None
    # cloud has no /api/info — only the spec is fetched
    assert calls == [fetch_spec.DEFAULT_SPEC_URL]


def test_resolve_sources_controller_base_url() -> None:
    args = fetch_spec.parse_args(["--base-url", "https://ctrl.example/"])
    spec_url, info_url, source = fetch_spec.resolve_sources(args, {})
    assert spec_url == "https://ctrl.example" + fetch_spec.SPEC_PATH_SUFFIX
    assert info_url == "https://ctrl.example/api/info"
    assert source == "controller"


def test_resolve_sources_explicit_controller_url_derives_info() -> None:
    args = fetch_spec.parse_args(["--url", "https://ctrl.example" + fetch_spec.SPEC_PATH_SUFFIX])
    spec_url, info_url, source = fetch_spec.resolve_sources(args, {})
    assert spec_url == "https://ctrl.example" + fetch_spec.SPEC_PATH_SUFFIX
    assert info_url == "https://ctrl.example/api/info"
    assert source == "controller"


def test_resolve_sources_default_is_cloud_without_info() -> None:
    args = fetch_spec.parse_args([])
    spec_url, info_url, source = fetch_spec.resolve_sources(args, {})
    assert spec_url == fetch_spec.DEFAULT_SPEC_URL
    assert info_url is None
    assert source == "cloud"


def test_resolve_sources_env_base_url() -> None:
    args = fetch_spec.parse_args([])
    spec_url, info_url, source = fetch_spec.resolve_sources(args, {"OMADA_BASE_URL": "https://env-ctrl"})
    assert spec_url == "https://env-ctrl" + fetch_spec.SPEC_PATH_SUFFIX
    assert info_url == "https://env-ctrl/api/info"
    assert source == "controller"


def test_outputs_do_not_leak_controller_host(tmp_path: Path, monkeypatch) -> None:
    raw, manifest_path = _redirect_outputs(tmp_path, monkeypatch)
    monkeypatch.setattr(fetch_spec, "_load_url", _fake_loader([]))

    # 192.0.2.0/24 is TEST-NET-1 (RFC 5737), reserved for documentation.
    fetch_spec.main(["--base-url", "https://192.0.2.10:8043", "--insecure"])

    manifest_text = manifest_path.read_text(encoding="utf-8")
    raw_text = raw.read_text(encoding="utf-8")
    # neither the base-url host nor the servers-block host may reach committed files
    assert "192.0.2.10" not in manifest_text
    assert "192.0.2.10" not in raw_text
    # the omadac id from /api/info must not leak either
    assert "secret-omadac" not in manifest_text


def test_raw_spec_bytes_are_deterministic(tmp_path: Path, monkeypatch) -> None:
    raw, _ = _redirect_outputs(tmp_path, monkeypatch)
    monkeypatch.setattr(fetch_spec, "_load_url", _fake_loader([]))

    fetch_spec.main(["--base-url", "https://fake-controller", "--insecure"])
    first = raw.read_bytes()
    fetch_spec.main(["--base-url", "https://fake-controller", "--insecure"])
    second = raw.read_bytes()
    assert first == second


def test_resolve_verify_precedence() -> None:
    assert fetch_spec.resolve_verify(fetch_spec.parse_args(["--insecure"]), {}) is False
    assert fetch_spec.resolve_verify(fetch_spec.parse_args([]), {"OMADA_VERIFY": "false"}) is False
    assert fetch_spec.resolve_verify(fetch_spec.parse_args([]), {"OMADA_VERIFY": "true"}) is True
    assert fetch_spec.resolve_verify(fetch_spec.parse_args([]), {}) is True
