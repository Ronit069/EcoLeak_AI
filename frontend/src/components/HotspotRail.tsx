import { useState } from 'react'
import type { HotspotOutputItem } from '../lib/contracts'
import { fmtKg, fmtPct } from '../lib/format'
import { SeverityBadge } from './badges'

export function HotspotRail({ items }: { items: HotspotOutputItem[] }) {
  const [open, setOpen] = useState<string | null>(items[0]?.id ?? null)
  if (items.length === 0) {
    return (
      <div className="notice">
        <b>No hotspots detected.</b> Add activity data for this period, then re-run detection.
        Missing emission factors produce an explicit incomplete state — never a fabricated value.
      </div>
    )
  }
  const max = Math.max(...items.map(h => h.emissions_kgco2e), 1)
  return (
    <div role="list" aria-label="Ranked emission hotspots">
      {items.map(h => {
        const expanded = open === h.id
        return (
          <button
            key={h.id}
            role="listitem"
            className={`hotspot sev-${h.severity}`}
            aria-expanded={expanded}
            onClick={() => setOpen(expanded ? null : h.id)}
          >
            <span className="sev-rail" aria-hidden="true" />
            <span className="rank-cell" aria-hidden="true">
              {String(h.rank).padStart(2, '0')}<small>RANK</small>
            </span>
            <span>
              <span style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0 }}>#{h.rank} · {h.process_name ?? 'Unassigned process'}</h3>
                <SeverityBadge severity={h.severity} />
              </span>
              <span className="hotspot-meta">
                <span>Emissions <b>{fmtKg(h.emissions_kgco2e)}</b></span>
                <span>Share <b>{fmtPct(h.contribution_percent)}</b></span>
                <span>Intensity <b>{h.carbon_intensity?.toFixed(2) ?? '—'}</b></span>
                <span>Score <b>{h.hotspot_score?.toFixed(1) ?? '—'}</b></span>
                <span>{h.activity_category ?? ''}</span>
              </span>
              <span className="contrib" aria-hidden="true">
                <i style={{ width: `${(h.emissions_kgco2e / max) * 100}%` }} />
              </span>
              {expanded && h.explanation && (
                <span className="explain" style={{ display: 'block' }}>{h.explanation}</span>
              )}
            </span>
            <span className="mono" style={{ fontSize: '.8rem', color: 'var(--legend)' }} aria-hidden="true">
              {expanded ? '−' : '+'}
            </span>
          </button>
        )
      })}
    </div>
  )
}
