import { usePhase1Data, Loading } from './Dashboard'
import { RecommendationPlate } from '../components/RecommendationPlate'

export function RecommendationsPage() {
  const { recs, error } = usePhase1Data()
  if (error) return <div className="notice"><b>Failed to load.</b> {error}</div>
  if (!recs) return <Loading />
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Recommendations</h1>
          <p>Budget {recs.budget_limit?.toLocaleString('en-IN')} INR · {recs.recommendations.length} ranked interventions (live J2 ranks the full library) · LLM explains only, never invents numbers</p>
        </div>
        <span className="provenance">J2 live-with-fallback · final_score weighted · confidence 0–100</span>
      </div>
      {recs.recommendations.map(r => <RecommendationPlate key={r.id} rec={r} />)}
    </>
  )
}
