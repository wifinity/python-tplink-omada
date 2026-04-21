"""Validate fixed OpenAPI specification."""

from __future__ import annotations

import json
from pathlib import Path

from openapi_spec_validator import validate_spec

FIXED_SPEC_PATH = Path("spec/fixed/all-fixed.json")


def main() -> None:
    if not FIXED_SPEC_PATH.exists():
        raise SystemExit(f"Missing fixed spec at {FIXED_SPEC_PATH}. Run make spec-fix first.")
    spec = json.loads(FIXED_SPEC_PATH.read_text(encoding="utf-8"))
    validate_spec(spec)
    print(f"Validated {FIXED_SPEC_PATH}")


if __name__ == "__main__":
    main()
