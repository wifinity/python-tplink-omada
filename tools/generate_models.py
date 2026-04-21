"""Generate lightweight internal model metadata from fixed spec.

This keeps generated artifacts internal and stable while the public API remains dict-first.
"""

from __future__ import annotations

import json
from pathlib import Path
from pprint import pformat

import black

FIXED_SPEC_PATH = Path("spec/fixed/all-fixed.json")
MODELS_DIR = Path("omada_client/generated/models")
MODELS_FILE = MODELS_DIR / "schema_index.py"


def main() -> None:
    if not FIXED_SPEC_PATH.exists():
        raise SystemExit(f"Missing fixed spec at {FIXED_SPEC_PATH}. Run make spec-fix first.")

    spec = json.loads(FIXED_SPEC_PATH.read_text(encoding="utf-8"))
    schemas = spec.get("components", {}).get("schemas", {})

    schema_index = {name: schemas[name] for name in sorted(schemas.keys())}
    content = (
        '"""Auto-generated schema index from fixed OpenAPI spec.\n'
        "Do not edit manually.\n"
        '"""\n\n'
        f"SCHEMA_INDEX: dict[str, dict] = {pformat(schema_index, width=88)}\n"
    )

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    (MODELS_DIR / "__init__.py").write_text(
        '"""Generated internal model helpers."""\n\n' "from .schema_index import SCHEMA_INDEX as SCHEMA_INDEX\n",
        encoding="utf-8",
    )
    formatted_content = black.format_str(content, mode=black.Mode())
    MODELS_FILE.write_text(formatted_content, encoding="utf-8")
    print(f"Generated {MODELS_FILE}")


if __name__ == "__main__":
    main()
