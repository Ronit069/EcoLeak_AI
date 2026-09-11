"""EcoLeak AI - P3 Carbon Accounting & Simulation Engine.

Phase 1 implementation of Modules F, G, K, L (and stretch Module H).

Design constraints (see CONTRACTS_README.md, architecture doc §36):
- Modules F, G, K, L are pure deterministic Python. No LLM calls anywhere.
- scikit-learn is used only by Module H (anomaly detection).
- Output shapes are frozen by ``contracts/schemas.py``. The engine emits the
  contract DTOs (``HotspotDetectionResult`` etc.) so P1/P4 never change when the
  mock data source is swapped for P2's live ingestion API.
- Every calculation carries emission-factor version/source provenance so results
  remain reproducible after factors update.

The public entry point is :class:`engine.service.EcoLeakEngine`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the repository root importable so ``contracts.schemas`` resolves no matter
# which directory the process was launched from.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

__version__ = "phase1.0.0"

__all__ = ["__version__"]
