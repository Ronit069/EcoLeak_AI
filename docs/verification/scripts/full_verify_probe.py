"""Temporary black-box probe used for the full-system verification.

This file is intentionally disposable. It only uses HTTP against an already
running service; it does not import application internals or use the existing
test harness.
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from contracts.schemas import (
    DashboardResponse,
    HotspotDetectionResult,
    RecommendationGenerationResult,
    ScenarioSimulationEnvelope,
)


BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8011"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(r"C:\Temp\opencode\verify\live_probe.json")


def call(path: str, method: str = "GET", body: Any = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode()
    req_headers = {"Accept": "application/json"}
    if data is not None:
        req_headers["Content-Type"] = "application/json"
    req_headers.update(headers or {})
    req = Request(BASE + path, data=data, headers=req_headers, method=method)
    started = time.perf_counter()
    try:
        with urlopen(req, timeout=20) as response:
            raw = response.read()
            status = response.status
            response_headers = dict(response.headers.items())
    except HTTPError as exc:
        raw = exc.read()
        status = exc.code
        response_headers = dict(exc.headers.items())
    except (URLError, TimeoutError) as exc:
        return {"path": path, "method": method, "status": None, "error": repr(exc), "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}
    text = raw.decode("utf-8", errors="replace")
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError:
        payload = text
    return {
        "path": path,
        "method": method,
        "status": status,
        "headers": {k.lower(): v for k, v in response_headers.items()},
        "payload": payload,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def main() -> None:
    results: dict[str, Any] = {}
    context = call("/api/context")
    results["context"] = context
    ctx = context.get("payload") or {}
    facility = str((ctx.get("facilities") or [{}])[0].get("id", ""))
    period = str((ctx.get("reporting_periods") or [{}])[0].get("id", ""))
    base_period = f"/api/facilities/{facility}/reporting-periods/{period}"

    results["health"] = call("/api/health")
    results["inventory"] = call(base_period + "/inventory-summary")
    results["hotspots"] = call(base_period + "/hotspots")
    results["recommendations"] = call(base_period + "/recommendations")
    results["dashboard"] = call(base_period + "/dashboard")
    results["leak_map"] = call(base_period + "/leak-map")
    results["circularity"] = call(base_period + "/circularity-score")
    results["calculations"] = call(base_period + "/calculations", method="POST", body={})
    results["hotspots_detect"] = call(base_period + "/hotspots/detect", method="POST", body={})
    results["normalize"] = call("/api/units/normalize", method="POST", body={"value": 2, "from_unit": "MWh", "to_unit": "kWh"})
    results["normalize_ambiguous"] = call("/api/units/normalize", method="POST", body={"value": 2, "from_unit": "L", "to_unit": "m3"})
    results["normalize_unknown"] = call("/api/units/normalize", method="POST", body={"value": 2, "from_unit": "widgets", "to_unit": "kg"})

    recs = (results["recommendations"].get("payload") or {}).get("recommendations") or []
    rec_id = str(recs[0].get("id", "00000000-0000-4000-8000-000000000000")) if recs else "00000000-0000-4000-8000-000000000000"
    results["explanation_known"] = call(f"/api/recommendations/{rec_id}/explanation")
    results["explanation_unknown"] = call("/api/recommendations/00000000-0000-4000-8000-ffffffffffff/explanation")
    results["feedback_missing_type"] = call(f"/api/recommendations/{rec_id}/feedback", method="POST", body={})
    results["feedback_bad_reason"] = call(f"/api/recommendations/{rec_id}/feedback", method="POST", body={"feedback_type": "REJECTED", "reason_code": "NOT_A_REAL_CODE"})
    results["simulate_unknown_intervention"] = call(
        "/api/scenarios/00000000-0000-4000-8000-000000000000/simulate",
        method="POST",
        body={"facility_id": facility, "reporting_period_id": period, "interventions": [{"intervention_id": "00000000-0000-4000-8000-ffffffffffff"}]},
    )
    results["simulate_known"] = call(
        "/api/scenarios/00000000-0000-4000-8000-000000000000/simulate",
        method="POST",
        body={"facility_id": facility, "reporting_period_id": period, "interventions": []},
    )

    validation: dict[str, Any] = {}
    for name, model_key in (
        ("hotspots", HotspotDetectionResult),
        ("recommendations", RecommendationGenerationResult),
        ("dashboard", DashboardResponse),
        ("simulate_known", ScenarioSimulationEnvelope),
    ):
        try:
            model_key.model_validate(results[name].get("payload"))
            validation[name] = "PASS"
        except Exception as exc:  # validation evidence, not application behavior
            validation[name] = f"FAIL: {type(exc).__name__}: {exc}"
    results["contract_model_validation"] = validation

    errors = {}
    for name, value in results.items():
        if isinstance(value, dict) and value.get("status", 200) >= 400:
            payload = value.get("payload")
            errors[name] = {
                "status": value.get("status"),
                "keys": sorted(payload.keys()) if isinstance(payload, dict) else None,
                "frozen_shape": isinstance(payload, dict) and set(payload) == {"error_code", "message", "severity", "details"},
                "payload": payload,
            }
    results["error_shape_checks"] = errors

    load_target = BASE + "/api/health"

    def one(_: int) -> dict[str, Any]:
        return call("/api/health")

    started = time.perf_counter()
    concurrent: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=30) as pool:
        futures = [pool.submit(one, i) for i in range(50)]
        for future in as_completed(futures):
            concurrent.append(future.result())
    results["concurrency_health_50"] = {
        "count": len(concurrent),
        "status_counts": {str(code): sum(1 for row in concurrent if row.get("status") == code) for code in sorted({row.get("status") for row in concurrent}, key=str)},
        "max_elapsed_ms": max((row.get("elapsed_ms", 0) for row in concurrent), default=0),
        "total_elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "target": load_target,
    }

    OUT.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "base": BASE,
        "output": str(OUT),
        "context_status": context.get("status"),
        "facility": facility,
        "period": period,
        "contract_model_validation": validation,
        "errors": results["error_shape_checks"],
        "concurrency": results["concurrency_health_50"],
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
