"""Pins the HTTP contract (paths, methods, parameters, request/response schemas, status codes) to
a committed snapshot, so restructuring the backend can't silently change what the frontend sees.

operationId, tags, summary and description (operations and schemas) are left out — they only follow internal
function/router names and docstrings.
Regenerate deliberately with: UPDATE_OPENAPI_SNAPSHOT=1 python -m pytest tests/test_openapi_contract.py
"""

import json
import os
from pathlib import Path

from app.main import app

SNAPSHOT = Path(__file__).parent / "snapshots" / "openapi.json"


def _contract() -> dict:
    spec = json.loads(json.dumps(app.openapi()))
    for operations in spec["paths"].values():
        for operation in operations.values():
            for key in ("operationId", "tags", "summary", "description"):
                operation.pop(key, None)
    # A schema's description is its model class's docstring — documentation, not contract.
    for schema in spec.get("components", {}).get("schemas", {}).values():
        schema.pop("description", None)
    return {"paths": spec["paths"], "components": spec.get("components", {})}


def test_openapi_contract_matches_snapshot() -> None:
    contract = _contract()
    if os.environ.get("UPDATE_OPENAPI_SNAPSHOT") or not SNAPSHOT.exists():
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(contract, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    assert contract == json.loads(SNAPSHOT.read_text(encoding="utf-8"))
