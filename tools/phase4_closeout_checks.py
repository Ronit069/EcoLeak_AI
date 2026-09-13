"""Phase 4 closeout checks - module A-Q, edge cases, and regressions over the live API.

Assumes the merged backend is running (default http://localhost:8000) with a seeded
PostgreSQL database in live mode (USE_MOCK_DATA=false).

Run:  python tools/phase4_closeout_checks.py
Exit: 0 = all required checks pass, 1 = failures found (printed).
"""

from __future__ import annotations

import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

BASE = os.environ.get("ECOLEAK_BASE_URL", "http://localhost:8000")
ORG = "0a1b2c3d-0001-4001-8001-000000000001"
F = "0a1b2c3d-0002-4002-8002-000000000002"
P = "0a1b2c3d-0003-4003-8003-000000000003"
HEADERS = {"X-Role": "ORGANIZATION_ADMIN", "X-Organization-Id": ORG}

RESULTS: list[tuple[str, bool, str]] = []
client = httpx.Client(base_url=BASE, headers=HEADERS, timeout=60.0)
created_scenarios: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" :: {detail}" if detail else ""))
    return ok


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def get(path: str, **kw):
    return client.get(path, **kw)


def post(path: str, **kw):
    return client.post(path, **kw)


def main() -> int:
    print(f"=== Phase 4 closeout checks against {BASE} ===")
    health = get("/api/health")
    check(
        "ops: /api/health reports dependencies ok",
        health.status_code == 200 and health.json().get("status") == "ok",
        f"{health.status_code} {health.json().get('components') if health.status_code == 200 else health.text[:80]}",
    )

    # ---------------------------------------------------------------- Module A
    section("Module A - SME / facility profiling")
    ctx = get("/api/context").json()
    check(
        "A: /api/context returns organization + facility + reporting period",
        bool(ctx.get("organization")) and len(ctx.get("facilities", [])) >= 1 and len(ctx.get("reporting_periods", [])) >= 1,
        f"facilities={len(ctx.get('facilities', []))} periods={len(ctx.get('reporting_periods', []))}",
    )
    fac = get(f"/api/facilities/{F}")
    fac_body = fac.json() if fac.status_code == 200 else {}
    check(
        "A: facility profile carries size/location/production",
        fac.status_code == 200
        and float(fac_body.get("annual_production") or 0) == 1000.0
        and fac_body.get("country") == "India",
        f"{fac.status_code} production={fac_body.get('annual_production')} country={fac_body.get('country')}",
    )
    bad_prod = client.patch(f"/api/facilities/{F}", json={"working_days_per_year": 400})
    check("A edge: working_days_per_year > 366 rejected", bad_prod.status_code == 422, f"{bad_prod.status_code}")
    bad_period = post(
        f"/api/facilities/{F}/reporting-periods",
        json={"period_type": "CUSTOM", "start_date": "2026-01-01", "end_date": "2025-01-01"},
    )
    check("A edge: reporting period end_date < start_date rejected", bad_period.status_code == 422, f"{bad_period.status_code}")

    # ---------------------------------------------------------------- Module B
    section("Module B - process mapper")
    procs = get(f"/api/facilities/{F}/processes").json()
    names = {p["name"] for p in procs} if isinstance(procs, list) else set()
    check(
        "B: six demo processes present (Dyeing..Transportation)",
        {"Dyeing", "Drying", "Boiler", "Finishing", "Packaging", "Transportation"} <= names,
        f"count={len(names)}",
    )

    # ---------------------------------------------------------------- Module C
    section("Module C - data input & ingestion")
    acts = get(f"/api/facilities/{F}/activity", params={"reporting_period_id": P}).json()
    check("C: 13 seeded activity rows listed", isinstance(acts, list) and len(acts) == 13, f"count={len(acts)}")
    valid_csv = (
        "process_code,activity_category,activity_subcategory,original_value,original_unit,"
        "source_name,data_source_type,measured_or_estimated,confidence_score,notes\n"
        'PRC-BLR,FUEL,"Closeout dry-run row",111,L,"closeout-dryrun",CSV,MEASURED,90,""\n'
    )
    dry = post(
        f"/api/facilities/{F}/activity/import",
        data={"reporting_period_id": P, "dry_run": "true"},
        files={"file": ("closeout_valid.csv", valid_csv.encode(), "text/csv")},
    )
    body = dry.json() if dry.status_code in (200, 202) else {}
    check(
        "C: valid CSV dry-run accepted with no ERROR issues",
        dry.status_code in (200, 202) and not [i for i in body.get("row_issues", []) if i.get("severity") == "ERROR"],
        f"{dry.status_code} issues={len(body.get('row_issues', []))}",
    )
    neg_csv = valid_csv.replace('"Closeout dry-run row",111', '"Closeout negative row",-5')
    neg = post(
        f"/api/facilities/{F}/activity/import",
        data={"reporting_period_id": P, "dry_run": "true"},
        files={"file": ("closeout_negative.csv", neg_csv.encode(), "text/csv")},
    )
    neg_codes = {i.get("code") for i in (neg.json().get("row_issues", []) if neg.status_code in (200, 202) else [])}
    check("C edge: negative value surfaces NEGATIVE_VALUE (ERROR)", "NEGATIVE_VALUE" in neg_codes, f"{neg.status_code} codes={sorted(neg_codes)}")
    miss_csv = valid_csv.replace('"Closeout dry-run row",111,L', '"Closeout missing unit",111,')
    miss = post(
        f"/api/facilities/{F}/activity/import",
        data={"reporting_period_id": P, "dry_run": "true"},
        files={"file": ("closeout_missing_unit.csv", miss_csv.encode(), "text/csv")},
    )
    miss_codes = {i.get("code") for i in (miss.json().get("row_issues", []) if miss.status_code in (200, 202) else [])}
    check(
        "C edge: missing unit surfaces an ERROR issue",
        bool(miss_codes & {"MISSING_VALUE", "INVALID_UNIT"}),
        f"{miss.status_code} codes={sorted(miss_codes)}",
    )

    # ---------------------------------------------------------------- Module D
    section("Module D - unit normalization & data quality")
    conv = post("/api/units/normalize", json={"value": 1, "from_unit": "MWh", "to_unit": "kWh"})
    check(
        "D: MWh -> kWh normalized to 1000",
        conv.status_code == 200 and float(conv.json().get("normalized_value", 0)) == 1000.0,
        f"{conv.status_code} {conv.json().get('normalized_value') if conv.status_code == 200 else conv.text[:60]}",
    )
    ambiguous = post("/api/units/normalize", json={"value": 1, "from_unit": "L", "to_unit": "kg"})
    check(
        "D edge: L -> kg without density is CONFIRMATION_REQUIRED (422)",
        ambiguous.status_code == 422 and "CONFIRMATION" in ambiguous.text.upper(),
        f"{ambiguous.status_code}",
    )
    dq = get(f"/api/facilities/{F}/reporting-periods/{P}/data-quality")
    check("D: data-quality endpoint returns component scores", dq.status_code == 200, f"{dq.status_code}")

    # ---------------------------------------------------------------- Module E
    section("Module E - emission factor KB")
    factors_all = get("/api/emission-factors").json()
    factors = get("/api/emission-factors", params={"active": "true"}).json()
    check(
        "E: factor KB seeds 18 rows, 17 active versions",
        isinstance(factors_all, list) and len(factors_all) == 18 and len(factors) == 17,
        f"total={len(factors_all)} active={len(factors)}",
    )
    latest = get(
        "/api/emission-factors/lookup",
        params={
            "category": "ELECTRICITY",
            "activity_subcategory": "Purchased grid electricity - dyeing machinery (jet dyeing, padding)",
            "normalized_unit": "kWh",
            "region_country": "India",
        },
    )
    check(
        "E: prioritized lookup finds India grid factor with provenance",
        latest.status_code == 200
        and latest.json().get("total_co2e_factor") is not None
        and latest.json().get("version"),
        f"{latest.status_code} {latest.json().get('factor_code') if latest.status_code == 200 else latest.text[:80]}",
    )

    # ---------------------------------------------------------------- Module F
    section("Module F - carbon accounting")
    inv = get(f"/api/facilities/{F}/reporting-periods/{P}/inventory-summary").json()
    check(
        "F: scope totals match the seeded fixture exactly",
        float(inv.get("scope1_kgco2e", 0)) == 225560.8
        and float(inv.get("scope2_kgco2e", 0)) == 340800.0
        and float(inv.get("total_kgco2e", 0)) == 7203660.8,
        f"S1={inv.get('scope1_kgco2e')} S2={inv.get('scope2_kgco2e')} S3={inv.get('scope3_kgco2e')} total={inv.get('total_kgco2e')}",
    )
    calc_post = post(f"/api/facilities/{F}/reporting-periods/{P}/calculations", json={})
    calc_get = get(f"/api/facilities/{F}/reporting-periods/{P}/calculations")
    check(
        "F: calculations reproducible via GET (F2) and POST (F1) with same count",
        calc_post.status_code == 200 and calc_get.status_code == 200 and len(calc_post.json()) == len(calc_get.json()),
        f"POST={len(calc_post.json()) if calc_post.status_code == 200 else calc_post.status_code} "
        f"GET={len(calc_get.json()) if calc_get.status_code == 200 else calc_get.status_code}",
    )
    repro = [r for r in calc_get.json() if (r.get("assumptions") or {}).get("factor_code")]
    check(
        "F: resolved calculations retain factor code/version provenance",
        bool(repro) and all((r["assumptions"] or {}).get("factor_version") for r in repro),
        f"{len(repro)} resolved rows carry factor provenance",
    )

    # ---------------------------------------------------------------- Module G
    section("Module G - hotspot detector")
    hot = get(f"/api/facilities/{F}/reporting-periods/{P}/hotspots").json()
    hs = hot.get("hotspots", [])
    check(
        "G: 5 hotspots, Boiler top at 39.8% HIGH",
        len(hs) == 5 and hs[0]["process_name"] == "Boiler" and abs(float(hs[0]["contribution_percent"]) - 39.8263) < 0.01,
        f"{[(h['process_name'], h['severity']) for h in hs]}",
    )
    detect = post(f"/api/facilities/{F}/reporting-periods/{P}/hotspots/detect", json={})
    check("G: detect endpoint (G1) returns the frozen envelope", detect.status_code == 200, f"{detect.status_code}")

    # ---------------------------------------------------------------- Module H
    section("Module H - anomaly & inefficiency")
    an = post(f"/api/facilities/{F}/anomalies/detect", json={"reporting_period_id": P})
    an_hist = get(f"/api/facilities/{F}/reporting-periods/{P}/anomalies")
    check("H: detect (H1) and history (H2) respond", an.status_code == 200 and an_hist.status_code == 200,
          f"H1={an.status_code} H2={an_hist.status_code}")
    an_body = an.json() if an.status_code == 200 else {}
    check(
        "H: rules-only honesty (no overconfident ML claim on one period)",
        "ml" not in str(an_body.get("method", "")).lower() or an_body.get("ml_available") in (False, None),
        f"method={an_body.get('method')} ml_available={an_body.get('ml_available')}",
    )

    # ---------------------------------------------------------------- Module I
    section("Module I - circular intervention KB")
    ivs = get("/api/interventions").json()
    check("I: 19-entry P4 library served", isinstance(ivs, list) and len(ivs) == 19, f"count={len(ivs)}")

    # ---------------------------------------------------------------- Module J
    section("Module J - recommendation engine")
    j2 = get(f"/api/facilities/{F}/reporting-periods/{P}/recommendations")
    recs = j2.json().get("recommendations", []) if j2.status_code == 200 else []
    check(
        "J: J2 returns 18 ranked recs, top INT-SCRAP-004",
        j2.status_code == 200 and len(recs) == 18 and recs[0]["intervention_code"] == "INT-SCRAP-004",
        f"count={len(recs)} top={recs[0]['intervention_code'] if recs else 'none'} score={recs[0]['final_score'] if recs else '-'}",
    )
    j1 = post(
        f"/api/facilities/{F}/reporting-periods/{P}/recommendations/generate",
        json={"budget_limit": 150000},
    )
    low = j1.json().get("recommendations", []) if j1.status_code in (200, 202) else []
    check(
        "J edge: budget=150k filters all over-budget recs before ranking",
        bool(low) and all(float((r.get("impact") or {}).get("estimated_capex") or 0) <= 150000 for r in low),
        f"codes={[r['intervention_code'] for r in low]}",
    )
    j0 = post(
        f"/api/facilities/{F}/reporting-periods/{P}/recommendations/generate",
        json={"budget_limit": 0},
    )
    zero = j0.json().get("recommendations", []) if j0.status_code in (200, 202) else []
    zero_capex = [
        float((r.get("impact") or {}).get("estimated_capex"))
        for r in zero
        if (r.get("impact") or {}).get("estimated_capex") is not None
    ]
    check(
        "J edge: budget=0 returns the no-CAPEX action (not a crash)",
        bool(zero) and bool(zero_capex) and all(c == 0.0 for c in zero_capex),
        f"codes={[r['intervention_code'] for r in zero]} capex={zero_capex}",
    )

    # ---------------------------------------------------------------- Module K
    section("Module K - cost & CO2 simulator")
    sim_payload = {
        "facility_id": F,
        "reporting_period_id": P,
        "budget_limit": 5000000,
        "interventions": [
            {"intervention_id": r["intervention_id"], "adoption_percentage": 100} for r in recs[:5]
        ],
    }
    sim = post(f"/api/scenarios/{uuid.uuid4()}/simulate", json=sim_payload)
    sb = sim.json() if sim.status_code == 200 else {}
    a = sb.get("assessment") or {}
    check(
        "K: K1 returns the canonical envelope with a coherent assessment",
        sim.status_code == 200
        and {"scenario_id", "assessment", "interventions", "payback_status", "over_budget"} <= set(sb.keys())
        and float(a.get("baseline_emissions_kg", 0)) == 7203660.8
        and 0 <= float(a.get("projected_emissions_kg", -1)) <= float(a.get("baseline_emissions_kg", 0)),
        f"baseline={a.get('baseline_emissions_kg')} projected={a.get('projected_emissions_kg')} payback={a.get('payback_years')}",
    )
    bad_adopt = post(
        f"/api/scenarios/{uuid.uuid4()}/simulate",
        json={"facility_id": F, "reporting_period_id": P, "interventions": [{"intervention_id": recs[0]["intervention_id"], "adoption_percentage": 120}]},
    )
    check("K edge: adoption > 100 rejected", bad_adopt.status_code == 422, f"{bad_adopt.status_code}")

    # ---------------------------------------------------------------- Module L
    section("Module L - circularity score")
    cir = get(f"/api/facilities/{F}/reporting-periods/{P}/circularity-score").json()
    check(
        "L: score labelled as internal metric with disclaimer",
        cir.get("is_internal_metric") is True and bool(cir.get("disclaimer")),
        f"total={cir.get('total_score')} internal={cir.get('is_internal_metric')}",
    )

    # ---------------------------------------------------------------- Module M
    section("Module M - explainability")
    expl = get(f"/api/recommendations/{recs[0]['id']}/explanation")
    ex = expl.json() if expl.status_code == 200 else {}
    check(
        "M: M1 returns summary + evidence + assumptions + confidence",
        expl.status_code == 200
        and {"recommendation_id", "summary", "evidence", "assumptions", "confidence_score"} <= set(ex.keys())
        and len(ex.get("summary", "")) > 300,
        f"{expl.status_code} summary_len={len(ex.get('summary', ''))}",
    )
    check(
        "M: explanation text embeds the same numbers as the card",
        f"{recs[0]['impact']['estimated_co2_saving_kg']:.0f}".rstrip("0").rstrip(".") in ex.get("summary", "")
        or f"{int(float(recs[0]['impact']['estimated_co2_saving_kg'])):,}" in ex.get("summary", ""),
        "co2 saving present in narrative",
    )

    # ---------------------------------------------------------------- Module N
    section("Module N - dashboard & leak map")
    dash = get(f"/api/facilities/{F}/reporting-periods/{P}/dashboard")
    db = dash.json() if dash.status_code == 200 else {}
    check(
        "N: N1 exposes KPIs, scope breakdown and top actionable target",
        dash.status_code == 200
        and db.get("total_kgco2e") == 7203660.8
        and db.get("top_actionable_hotspot_id")
        and sum(float(v) for v in db.get("scope_breakdown", {}).values()) == 7203660.8,
        f"total={db.get('total_kgco2e')} actionable={bool(db.get('top_actionable_hotspot_id'))}",
    )
    lm = get(f"/api/facilities/{F}/reporting-periods/{P}/leak-map").json()
    check("N: N2 leak map returns 5 nodes", len(lm.get("nodes", [])) == 5, f"nodes={len(lm.get('nodes', []))}")

    # ---------------------------------------------------------------- Module O
    section("Module O - what-if / digital twin lite")
    created = post(f"/api/facilities/{F}/scenarios", json={"name": "Phase4 closeout probe", "budget_limit": 5000000})
    check("O1: create scenario", created.status_code == 201, f"{created.status_code}")
    if created.status_code == 201:
        sid = created.json()["id"]
        created_scenarios.append(sid)
        listed = get(f"/api/facilities/{F}/scenarios").json()
        clone = post(f"/api/scenarios/{sid}/clone")
        check(
            "O2/O5: list contains scenario and clone succeeds",
            any(s["id"] == sid for s in listed.get("scenarios", [])) and clone.status_code == 201,
            f"listed={len(listed.get('scenarios', []))} clone={clone.status_code}",
        )
        if clone.status_code == 201:
            created_scenarios.append(clone.json()["id"])
    else:
        check("O2/O5: list + clone", False, f"create failed: {created.text[:120]}")

    # ---------------------------------------------------------------- Module P
    section("Module P - compliance & sustainability report")
    rep = post(f"/api/facilities/{F}/reporting-periods/{P}/reports", json={"template_version": "closeout", "include_scope3": True})
    check("P1: report accepted (202 receipt)", rep.status_code == 202, f"{rep.status_code}")
    if rep.status_code == 202:
        detail = get(f"/api/reports/{rep.json()['report_id']}").json()
        payload = detail.get("payload", {})
        unresolved = [p for p in payload.get("factor_provenance", []) if p.get("status") == "UNRESOLVED"]
        check(
            "P2: report carries scope, provenance, DQ, recommendations",
            all(k in payload for k in ("profile", "boundary", "factor_provenance", "scope_summary", "data_quality_score", "hotspot_analysis", "recommendations"))
            and payload.get("scope_summary", {}).get("total_kgco2e") == 7203660.8
            and bool(payload.get("factor_provenance")),
            f"sections={len(payload)} unresolved={len(unresolved)}",
        )
        check(
            "P edge: unresolved rows expose category under details (BUG-4-01 UI reads this)",
            all((p.get("details") or {}).get("activity_category") for p in unresolved) if unresolved else True,
            f"unresolved={[(p.get('details') or {}).get('activity_category') for p in unresolved]}",
        )

    # ---------------------------------------------------------------- Module Q
    section("Module Q - feedback")
    fb = post(f"/api/recommendations/{recs[0]['id']}/feedback", json={"feedback_type": "USEFUL"})
    hist = get(f"/api/recommendations/{recs[0]['id']}/feedback").json()
    check(
        "Q1/Q2: feedback stored and history returns latest state",
        fb.status_code == 201 and hist.get("latest_state", {}).get("feedback_type") == "USEFUL",
        f"post={fb.status_code} latest={hist.get('latest_state', {}).get('feedback_type')}",
    )
    bad_fb = post(f"/api/recommendations/{recs[0]['id']}/feedback", json={"feedback_type": "BOGUS"})
    check("Q edge: invalid feedback_type -> 422 frozen shape (P4-M1 no regression)", bad_fb.status_code == 422, f"{bad_fb.status_code}")

    # ---------------------------------------------------------------- cleanup
    for sid in created_scenarios:
        client.delete(f"/api/scenarios/{sid}")

    failures = [name for name, ok, _ in RESULTS if not ok]
    print("\n=== SUMMARY ===")
    print(f"{len(RESULTS) - len(failures)}/{len(RESULTS)} checks passed")
    for name in failures:
        print(f"  FAILED: {name}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
