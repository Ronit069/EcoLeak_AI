"""Run the full textile SME demo through the P4 engine (deterministic).

    python -m p4.demo.run_demo                      # mock hotspots (default)
    python -m p4.demo.run_demo --use-mock-data false  # live P3 hotspots (needs DSN)

Phase 2: the hotspot input is flag-gated via ``p4.data_source`` (shared
``USE_MOCK_DATA`` rule). Default behavior is the Phase 1 mock fixture so
``main`` stays demo-able with zero DB dependencies. Live mode reads P3's
Engine G output over the flag-selected data source, derives the P4 estimator
factors from the live versioned factor KB, and writes a separate artifact
(``demo_recommendation_output.live.json``) so the mock demo output is never
overwritten.

Both modes verify the output shape against
``mocks/mock_recommendation_output.json`` and write explanations under
``p4/demo/output/``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from p4.contracts import (  # noqa: E402
    Facility,
    Organization,
    Process,
    RecommendationGenerationResult,
)
from p4.data_source import (  # noqa: E402
    load_facility_dataset,
    load_hotspots,
    resource_factors_from_dataset,
    resource_factors_from_factors,
)
from p4.engine import generate_with_diagnostics  # noqa: E402
from p4.explainability import TemplateExplainer  # noqa: E402
from p4.models import (  # noqa: E402
    FacilityContext,
    RecommendationConstraints,
    ResourceEmissionFactors,
)
from p4.serialization import to_api_dict  # noqa: E402

MOCKS_DIR = PROJECT_ROOT / "mocks"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


FREEFORM_KEYS = {"assumptions"}


def _shape_diff(left, right, path: str = "$") -> list[str]:
    """Recursively compare JSON key sets (values may differ).

    Free-form JSONB blobs (impact.assumptions) are treated as opaque: their
    inner keys are implementation detail, not frozen contract.
    """

    problems: list[str] = []
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) - set(right)):
            problems.append(f"{path}.{key}: missing from generated output")
        for key in sorted(set(right) - set(left)):
            problems.append(f"{path}.{key}: unexpected in generated output")
        for key in sorted(set(left) & set(right)):
            if key in FREEFORM_KEYS:
                continue
            problems.extend(_shape_diff(left[key], right[key], f"{path}.{key}"))
    elif isinstance(left, list) and isinstance(right, list):
        if left and right:
            problems.extend(_shape_diff(left[0], right[0], f"{path}[0]"))
    return problems


def _resource_factors(dataset: dict) -> ResourceEmissionFactors:
    """Mock-dataset estimator factors (kept stable: P2's bridge imports this)."""

    return resource_factors_from_dataset(dataset)


def _mock_inputs() -> tuple[Organization, Facility, list[Process], ResourceEmissionFactors]:
    dataset = _load_json(MOCKS_DIR / "mock_dataset.json")
    return (
        Organization.model_validate(dataset["organization"]),
        Facility.model_validate(dataset["facilities"][0]),
        [Process.model_validate(item) for item in dataset["processes"]],
        _resource_factors(dataset),
    )


def _live_inputs(engine, facility_id) -> tuple[Organization | None, Facility, list[Process], ResourceEmissionFactors]:
    organization, facility, processes = load_facility_dataset(engine, str(facility_id))
    factors = resource_factors_from_factors(
        engine.data_source.get_emission_factors(), region_country=facility.country
    )
    return organization, facility, processes, factors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EcoLeak AI P4 demo runner")
    parser.add_argument(
        "--use-mock-data",
        choices=("true", "false", "legacy"),
        default="legacy",
        help="Hotspot source gate: true=mock, false=live P3, legacy=env/DSN rule",
    )
    args = parser.parse_args(argv)
    explicit = {"true": True, "false": False, "legacy": None}[args.use_mock_data]

    hotspot_source = load_hotspots(use_mock_data=explicit, fallback_to_mock=True)
    for warning in hotspot_source.warnings:
        print(f"WARNING: {warning}")
    hotspots = hotspot_source.envelope
    if hotspot_source.source == "live":
        organization, facility, processes, factors = _live_inputs(
            hotspot_source.engine, hotspots.facility_id
        )
        output_path = OUTPUT_DIR / "demo_recommendation_output.live.json"
    else:
        organization, facility, processes, factors = _mock_inputs()
        output_path = OUTPUT_DIR / "demo_recommendation_output.json"

    context = FacilityContext.model_validate(_load_json(Path(__file__).parent / "demo_context.json"))
    if str(context.facility_id) != str(facility.id) or str(context.reporting_period_id) != str(
        hotspots.reporting_period_id
    ):
        print(
            "WARNING: demo_context.json is keyed to the demo facility/period; "
            "financial estimates are incomplete for this dataset"
        )
        context = None

    run = generate_with_diagnostics(
        hotspots,
        facility,
        organization=organization,
        processes=processes,
        context=context,
        emission_factors=factors,
        constraints=RecommendationConstraints(
            budget_limit=5_000_000,
            region_country="India",
            region_state="Gujarat",
        ),
        explainer=TemplateExplainer(),
    )

    generated = to_api_dict(run.result)
    expected = _load_json(MOCKS_DIR / "mock_recommendation_output.json")
    shape_problems = _shape_diff(generated, expected)
    if shape_problems:
        print("SHAPE MISMATCH vs mocks/mock_recommendation_output.json:")
        for problem in shape_problems:
            print("  -", problem)
        return 1
    print("Shape check vs mocks/mock_recommendation_output.json: PASS")

    RecommendationGenerationResult.model_validate(generated)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(generated, indent=2), encoding="utf-8")

    print()
    print(f"Hotspot source: {hotspot_source.source}")
    print(f"Baseline: {hotspots.total_emissions_kgco2e:,.0f} kgCO2e "
          f"(scope {', '.join(scope.value for scope in hotspots.scope_boundary)}), "
          f"data quality {hotspots.data_quality_score}")
    print(f"Considered {run.diagnostics.considered} interventions | "
          f"ranked {len(run.result.recommendations)} | "
          f"filtered {len(run.diagnostics.filtered)}")
    print()
    header = f"{'#':>2}  {'final':>6}  {'capex':>12}  {'saving/yr':>12}  {'payback':>8}  {'CO2e kg/yr':>10}  code"
    print(header)
    print("-" * len(header))
    for rec in run.result.recommendations:
        impact = rec.impact
        capex = f"{impact.estimated_capex:,.0f}" if impact.estimated_capex is not None else "n/a"
        saving = f"{impact.estimated_annual_saving:,.0f}" if impact.estimated_annual_saving is not None else "n/a"
        payback = f"{impact.payback_years}" if impact.payback_years is not None else "n/a"
        co2 = f"{impact.estimated_co2_saving_kg:,.0f}" if impact.estimated_co2_saving_kg is not None else "n/a"
        print(f"{rec.rank:>2}  {rec.final_score:>6}  {capex:>12}  {saving:>12}  {payback:>8}  {co2:>10}  {rec.intervention_code}")

    if run.diagnostics.conflicts:
        print("\nMutually exclusive pairs in the ranked set:")
        for pair in run.diagnostics.conflicts:
            print("  -", " <> ".join(pair))
    if run.diagnostics.warnings:
        print("\nWarnings:")
        for warning in run.diagnostics.warnings:
            print("  -", warning)

    explanations_path = OUTPUT_DIR / (
        "demo_explanations.live.md"
        if hotspot_source.source == "live"
        else "demo_explanations.md"
    )
    lines = [
        "# EcoLeak AI demo - recommendation explanations",
        "",
        f"Hotspot source: {hotspot_source.source}",
        f"Baseline operational emissions: {hotspots.total_emissions_kgco2e:,.0f} kgCO2e "
        f"({', '.join(scope.value for scope in hotspots.scope_boundary)}), "
        f"data quality {hotspots.data_quality_score}/100.",
        "",
    ]
    for rec in run.result.recommendations:
        lines += [
            f"## #{rec.rank} {rec.intervention_code} - {rec.intervention_title} "
            f"(score {rec.final_score})",
            "",
            rec.explanation or "",
            "",
        ]
    explanations_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nWrote {output_path}")
    print(f"Wrote {explanations_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
