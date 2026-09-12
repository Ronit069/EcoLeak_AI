import { usePhase1Data, Loading } from './Dashboard'
import { RecommendationPlate } from '../components/RecommendationPlate'

export function RecommendationsPage() {
  const { recs, error } = usePhase1Data()
  if (error) return <div className="notice"><b>Failed to load.</b> {error}</div>
  if (!recs) return <Loading />
  // F-8: financial baselines are still the P4 demo fixture; surface it loudly
  // (the same signal is machine-readable per item at impact.assumptions.data_is_stub).
  const usesFixtureFinancials = recs.recommendations.some(
    r => (r.impact?.assumptions as Record<string, unknown> | null | undefined)?.data_is_stub === true
  )
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Recommendations</h1>
          <p>Budget {recs.budget_limit?.toLocaleString('en-IN')} INR · {recs.recommendations.length} ranked interventions (live J2 ranks the full library) · LLM explains only, never invents numbers</p>
        </div>
        <span className="provenance">J2 live-with-fallback · final_score weighted · confidence 0–100</span>
      </div>
      {usesFixtureFinancials && (
        <div className="notice" role="status">
          <b>Fixture financial baselines.</b> CAPEX/savings use the P4 demo tariff fixture
          (<code>data_is_stub=true</code>); treat payback and savings as provisional until real cost data is wired.
        </div>
      )}
      {recs.recommendations.map(r => <RecommendationPlate key={r.id} rec={r} />)}
    </>
  )
}
