# Phase 2 — Process Notes (remediation record)

**Created:** phase2-fixes remediation (PHASE2_AUDIT.md BLOCKER 3)

## 1. Recorded process violations (cannot rewrite merged history)

| Violation | Commits | Recorded action |
|---|---|---|
| Phase 2 work pushed **directly to `main`** (no branch/PR/merge record) by P2 | `7f5ead4` feat(p2-phase2) | Documented here; branches `phase2-p2`/`phase2-p3` created after the fact point at the same commits. Logs + PR descriptions exist (`docs/phase2/p2_pr_description.md`, `p3_pr_description.md`), so intent was documented, but the shared "test in your branch, do not merge until log complete" rule was violated |
| Same, P3 | `a0a6aa9` feat(p3-phase2) | Same as above |

## 2. Branch protection on `main`

**Attempted during remediation (executed):**

```
$ gh api repos/Ronit069/EcoLeak_AI/branches/main/protection
-> 404 (no protection configured)
$ gh api -X PUT repos/Ronit069/EcoLeak_AI/branches/main/protection ... 
-> 404
$ gh api repos/Ronit069/EcoLeak_AI --jq .permissions
-> {"admin":false,"push":true,...}   (push-only rights)
```

Branch protection requires **admin** rights; the acting account has push-only.
**Required owner action (Ronit069):** enable protection on `main` with
`required_pull_request_reviews.required_approving_review_count = 1`,
`allow_force_pushes = false`, `allow_deletions = false` (Settings → Branches →
Add rule → `main`). Until applied, the GitHub-side guard cannot be enforced —
this is recorded, not silently dropped.

## 3. Sequencing gate (baseline → swap → diff) — live re-verification

Original commits each bundled baseline+swap+diff in one commit, so
commit-level ordering was not provable. Re-ran the documented process live on
the remediation branch and saved timestamped artifacts:

- `docs/phase2/p3_baseline_output_verified_20260912-130454.json` (generated fresh)
- `docs/phase2/p3_real_data_output_verified_20260912-130454.json`
- `docs/phase2/p4_baseline_output_verified_20260912-130454.json`
- `docs/phase2/p4_real_data_output_verified_20260912-130454.json`
- Re-diffs: `docs/phase2/p3_shape_diff.md`, `p4_shape_diff.md` (regenerated; all sections IDENTICAL — PASS)

## 4. Module H / Module Q — explicit decision (no limbo)

| Module | Decision | Evidence |
|---|---|---|
| H1 (anomalies detect) | Already served (`engine/api.py` `POST /api/facilities/{id}/anomalies/detect`) | route + `engine/anomaly.py` + `tests/test_anomaly.py` |
| H2 (GET anomalies) / H3 (acknowledge) | **Phase-3 backlog, owner P3** — requires anomaly persistence (no table-backed store yet in the merged surface) | recorded in `docs/phase2/contract_changes.md` §Remediation |
| Q1/Q2 (feedback) | **Wired into the merged surface now** (`p4/api.py` routes; in-memory append-only store from Phase 1; frozen error shape for guard failures) | `tests/test_remediation.py::test_q1_* / test_q2_*` (4/4 pass) |
| Q persistence (SQLAlchemy) | Phase-3 backlog, owner P2 | recorded in contract_changes |

## 5. Remediation scope discipline

This branch (`phase2-fixes`) contains only remediation changes; the previous
audit's commit `4a56f59` (docs + P1 K1 normalization) was itself a direct
push to main, acknowledged in PHASE2_AUDIT.md's own process findings — this
remediation is branch-based per the remediation instructions.
## Verification anti-patterns found in K1 remediation (for future contributors)

Two separate false-positive "verified" claims happened here, for two different
reasons. Both are now guarded by permanent checks (see the `K1-adversarial`
job in `.github/workflows/phase2-ci.yml`).

- **Anti-pattern 1 — loose assertions.** A test accepted `engine` or
  `local_fallback` interchangeably (`assert status == 200` with no field
  check, or `in {set}` unions spanning both success AND failure values).
  Fix claimed, test green, bug live. Habit: any test claiming to verify a
  fix MUST assert the distinguishing value ONLY (e.g. `computedVia ==
  'engine'`), never a superset. Grep reviews for `in {` / `or` unions near
  success/failure vocabularies.
- **Anti-pattern 2 — env indirection silently breaking build tooling.**
  `getEnv()` indirection made Vite's static `import.meta.env.X` replacement
  no-op silently, so both correct and broken backend targets produced
  IDENTICAL bundles and identical UI labels (masked further by the vite
  proxy routing relative `/api` to the fixed backend). The dual-state test
  (working vs deliberately-broken backend) is what caught it. Habit: for
  any fix that claims to make broken behavior VISIBLY different, test BOTH
  states with proxy-free serving and assert the baked artifacts differ.
