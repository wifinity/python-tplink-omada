"""Normalize and patch Omada OpenAPI spec."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

RAW_SPEC_PATH = Path("spec/raw/all.json")
FIXED_SPEC_PATH = Path("spec/fixed/all-fixed.json")
PATCH_DIR = Path("spec/patches")


def _pascal_case(value: str) -> str:
    chunks = re.split(r"[^A-Za-z0-9]+", value)
    return "".join(chunk[:1].upper() + chunk[1:] for chunk in chunks if chunk) or "Schema"


def _sanitize_schema_names(spec: dict[str, Any]) -> dict[str, str]:
    schemas = spec.setdefault("components", {}).setdefault("schemas", {})
    rename_map: dict[str, str] = {}
    used: set[str] = set(schemas.keys())

    for name in list(schemas.keys()):
        clean = _pascal_case(name)
        if clean != name:
            candidate = clean
            idx = 2
            while candidate in used:
                candidate = f"{clean}{idx}"
                idx += 1
            rename_map[name] = candidate
            used.add(candidate)

    for old, new in rename_map.items():
        schemas[new] = schemas.pop(old)

    return rename_map


def _rewrite_refs(node: Any, rename_map: dict[str, str]) -> Any:
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                prefix = "#/components/schemas/"
                if value.startswith(prefix):
                    old = value.removeprefix(prefix)
                    if old in rename_map:
                        out[key] = prefix + rename_map[old]
                        continue
            out[key] = _rewrite_refs(value, rename_map)
        return out
    if isinstance(node, list):
        return [_rewrite_refs(item, rename_map) for item in node]
    return node


def _ensure_security(spec: dict[str, Any]) -> None:
    components = spec.setdefault("components", {})
    schemes = components.setdefault("securitySchemes", {})
    schemes["AccessToken"] = {
        "type": "apiKey",
        "in": "header",
        "name": "Authorization",
    }
    spec["security"] = [{"AccessToken": []}]


def _extract_path_params(path: str) -> set[str]:
    return set(re.findall(r"\{([A-Za-z0-9_]+)\}", path))


def _add_missing_path_params(spec: dict[str, Any]) -> None:
    paths = spec.get("paths", {})
    for path, item in paths.items():
        required_params = _extract_path_params(path)
        if not required_params or not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            if not isinstance(operation, dict):
                continue
            params = operation.setdefault("parameters", [])
            existing = {p.get("name") for p in params if isinstance(p, dict) and p.get("in") == "path"}
            for param in sorted(required_params - existing):
                params.append(
                    {
                        "name": param,
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                )


def _collect_refs(node: Any, refs: set[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                refs.add(value)
            else:
                _collect_refs(value, refs)
    elif isinstance(node, list):
        for item in node:
            _collect_refs(item, refs)


def _ensure_placeholder_schemas(spec: dict[str, Any]) -> None:
    refs: set[str] = set()
    _collect_refs(spec, refs)
    schemas = spec.setdefault("components", {}).setdefault("schemas", {})
    prefix = "#/components/schemas/"
    for ref in sorted(refs):
        if ref.startswith(prefix):
            name = ref.removeprefix(prefix)
            if name not in schemas:
                schemas[name] = {
                    "type": "object",
                    "description": "Auto-generated placeholder for missing schema",
                    "additionalProperties": True,
                }


def _strip_patterns(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _strip_patterns(v) for k, v in node.items() if k != "pattern"}
    if isinstance(node, list):
        return [_strip_patterns(item) for item in node]
    return node


def _deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, dict) and isinstance(overlay, dict):
        merged = dict(base)
        for key, value in overlay.items():
            merged[key] = _deep_merge(merged[key], value) if key in merged else copy.deepcopy(value)
        return merged
    if isinstance(base, list) and isinstance(overlay, list):
        return copy.deepcopy(overlay)
    return copy.deepcopy(overlay)


def _load_patch_files() -> list[Path]:
    if not PATCH_DIR.exists():
        return []
    files = [p for p in PATCH_DIR.iterdir() if p.suffix in {".json"}]
    return sorted(files)


def main() -> None:
    if not RAW_SPEC_PATH.exists():
        raise SystemExit(f"Missing raw spec at {RAW_SPEC_PATH}. Run make spec-fetch first.")

    spec = json.loads(RAW_SPEC_PATH.read_text(encoding="utf-8"))
    rename_map = _sanitize_schema_names(spec)
    spec = _rewrite_refs(spec, rename_map)
    _ensure_security(spec)
    _add_missing_path_params(spec)
    _ensure_placeholder_schemas(spec)
    spec = _strip_patterns(spec)

    for patch_file in _load_patch_files():
        patch = json.loads(patch_file.read_text(encoding="utf-8"))
        spec = _deep_merge(spec, patch)

    FIXED_SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXED_SPEC_PATH.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote patched spec to {FIXED_SPEC_PATH}")


if __name__ == "__main__":
    main()
