"""Load the frozen Phase 0 contract module as the single source of truth.

`contracts/schemas.py` is intentionally NOT copied: P2, P1, P3 and P4 all import
the same file so field names cannot drift. We load it by path because the
contracts folder lives at the repository root (outside the backend package).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "schemas.py"


def _load() -> ModuleType:
    if not _CONTRACT_PATH.exists():  # pragma: no cover - guarded at startup
        raise RuntimeError(
            f"Frozen contract not found at {_CONTRACT_PATH}. "
            "Run `git pull` to fetch contracts/schemas.py."
        )
    spec = importlib.util.spec_from_file_location("ecoleak_contract_schemas", _CONTRACT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


schemas = _load()
