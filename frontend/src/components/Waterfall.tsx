// Scenario waterfall: baseline → per-intervention reductions → projected.
import { fmtCo2e } from '../lib/format'

interface Props {
  baseline: unknown
  projected: unknown
  reductions: Array<{ label: string; value: unknown }>
}

export function Waterfall({ baseline, projected, reductions }: Props) {
  return (
    <div className="wf">
      <div className="wrow total"><span className="lbl">BASELINE</span><span className="val">{fmtCo2e(baseline)}</span></div>
      {reductions.map((r) => (
        <div className="wrow decr" key={r.label}>
          <span className="lbl">↓ {r.label}</span>
          <span className="val">−{fmtCo2e(r.value)}</span>
        </div>
      ))}
      <div className="wrow total"><span className="lbl">PROJECTED</span><span className="val">{fmtCo2e(projected)}</span></div>
    </div>
  )
}
