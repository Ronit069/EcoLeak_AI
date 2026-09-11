"""Module I - intervention knowledge base tests."""

from p4.library import InterventionLibrary, default_library
from p4.models import LoopType

PHASE0_CODES = {
    "INT-WHR-001",
    "INT-SOLAR-002",
    "INT-DYEBATH-003",
    "INT-SCRAP-004",
    "INT-PKG-005",
}


def test_library_has_15_to_20_entries():
    library = default_library()
    assert 15 <= len(library) <= 20, f"expected 15-20 entries, got {len(library)}"


def test_phase0_interventions_preserved_and_codes_unique():
    library = default_library()
    assert PHASE0_CODES.issubset(library.codes())
    codes = [entry.intervention_code for entry in library.all()]
    assert len(codes) == len(set(codes))


def test_every_entry_has_reference_technical_requirements_and_loops():
    for entry in default_library().all():
        assert entry.evidence_source, f"{entry.intervention_code} missing evidence source"
        assert entry.technical_requirements, f"{entry.intervention_code} missing technical requirements"
        assert entry.loop_types, f"{entry.intervention_code} missing loop types"


def test_loop_coverage_for_all_required_areas():
    loops = {loop for entry in default_library().all() for loop in entry.loop_types}
    assert {
        LoopType.ENERGY,
        LoopType.HEAT_RECOVERY,
        LoopType.MATERIAL,
        LoopType.WATER,
        LoopType.WASTE,
        LoopType.PACKAGING,
        LoopType.CHEMICAL,
    }.issubset(loops)


def test_library_rejects_duplicate_codes():
    library = default_library()
    entry = library.all()[0]
    try:
        InterventionLibrary([entry, entry])
    except ValueError as exc:
        assert "duplicate intervention_code" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("duplicate codes must be rejected")


def test_get_unknown_code_raises():
    try:
        default_library().get("INT-DOES-NOT-EXIST")
    except KeyError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("unknown code must raise")
