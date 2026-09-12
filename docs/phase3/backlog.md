# Phase 3 Backlog (explicitly deferred, owned)

Items deferred by the full-system verification (`docs/verification/FULL_SYSTEM_VERIFICATION.md`)
and the Phase-3 readiness pass. Nothing here is silently dropped; each has an
owner and the reason it is deferred.

| Item | Finding | Why deferred | Owner |
|---|---|---|---|
| Provenance polish: uniform `computedVia`-style signal on every degrade path (server side, not only K1 frontend) | F-9 | Cosmetic-to-silent; Phase-3 feature work will touch these paths | P3/P4 |
| Distributed rate limiting (Redis-backed) + multi-worker semantics | F-10 | Needed before real scale, not before Phase 3 start | P2 |
| Query/statement timeouts + pool sizing (`pool_size`, `max_overflow`, `pool_timeout`; a bounded connect timeout is already in place) | F-11 | Needed before real scale | P2 |
| LLM narrative guardrail hardening: catch `MtCO2e`-style unit evasion and qualitative compliance/guarantee hallucinations (numeric + citation + low-confidence checks exist) | F-12 | Ranking is unaffected (LLM only writes narrative); hardening needs a policy decision on allowed claim vocabulary | P4 |
| J3 recommendation status + Q feedback persistence to SQLAlchemy | R11 | In-memory stores are wired and behaviorally correct; persistence is a P2 store swap | P2 |
| Module H2 (GET anomalies) / H3 (acknowledge) routers + anomaly persistence | PHASE2_AUDIT H | Needs a table-backed anomaly store on the merged surface | P3 |
| Repo-wide lint debt (`ruff check engine p4 tests` = 637 findings; backend `app/` is clean under the configured gate) | F-16 | Hygiene only; the enforced gate stays green | all |
| `frontend` `npm run validate` points at a missing `scripts/validate-mocks.ts` | F-17 | Script hygiene; mock validation runs in CI via the repo-root validators | P1 |
| Loosely-typed contract subtrees (`dict[str, Any]` in `largest_hotspot`, `K1 interventions[]/issues[]`) | F-18 | No consumer breakage; formal typing is a contract-evolution task | P4/P1 |
| Branch protection enforcement on `main` | T0-1 step 5 | Requires repo-owner admin; settings documented in `docs/phase3/READINESS.md` | Ronit069 |
