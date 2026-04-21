from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import fix_spec


def test_fix_spec_adds_missing_path_params_and_security(
    tmp_path: Path,
    monkeypatch,
) -> None:
    raw = tmp_path / "raw.json"
    fixed = tmp_path / "fixed.json"
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()

    raw_payload = {
        "openapi": "3.0.1",
        "paths": {"/openapi/v1/sites/{siteId}/devices": {"post": {"responses": {"200": {"description": "ok"}}}}},
        "components": {"schemas": {"bad-name": {"type": "object", "pattern": "^x$"}}},
    }
    raw.write_text(json.dumps(raw_payload), encoding="utf-8")

    patch_payload = {"paths": {"/x": {"get": {"operationId": "x"}}}}
    (patch_dir / "p.json").write_text(json.dumps(patch_payload), encoding="utf-8")

    monkeypatch.setattr(fix_spec, "RAW_SPEC_PATH", raw)
    monkeypatch.setattr(fix_spec, "FIXED_SPEC_PATH", fixed)
    monkeypatch.setattr(fix_spec, "PATCH_DIR", patch_dir)

    fix_spec.main()

    result = json.loads(fixed.read_text(encoding="utf-8"))
    op = result["paths"]["/openapi/v1/sites/{siteId}/devices"]["post"]
    path_params = [p for p in op["parameters"] if p["in"] == "path"]

    assert any(p["name"] == "siteId" for p in path_params)
    assert "AccessToken" in result["components"]["securitySchemes"]
    assert result["security"] == [{"AccessToken": []}]
    assert "BadName" in result["components"]["schemas"]
    assert "pattern" not in result["components"]["schemas"]["BadName"]
    assert "/x" in result["paths"]
