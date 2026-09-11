import type { HotspotSeverity } from '../lib/contracts'

const ICONS: Record<HotspotSeverity, { label: string; path: string }> = {
  CRITICAL: {
    label: 'Critical',
    path: 'M12 2 L22 20 H2 Z M12 9v5 M12 17.2v.3'
  },
  HIGH: {
    label: 'High',
    path: 'M12 3v10 M12 17.2v.3 M5 7l7-4 7 4 M5 7v10l7 4 7-4V7'
  },
  MODERATE: {
    label: 'Moderate',
    path: 'M4 12h16 M4 12l3-3 M4 12l3 3 M20 12l-3-3 M20 12l-3 3'
  },
  LOW: {
    label: 'Low',
    path: 'M12 19v-6 M12 13l-4-4 M12 13l4-4 M5 21h14'
  }
}

export function SeverityBadge({ severity }: { severity: HotspotSeverity }) {
  const icon = ICONS[severity]
  return (
    <span className="sev-badge" title={`Severity: ${icon.label}`}>
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d={icon.path} />
      </svg>
      {icon.label.toUpperCase()}
    </span>
  )
}

export function ScoreMeter({ label, value }: { label: string; value: number | null | undefined }) {
  const v = value ?? 0
  return (
    <div className="score">
      <label>{label} <b>{value == null ? '—' : v.toFixed(1)}</b></label>
      <div className="meter" role="img" aria-label={`${label} ${value ?? 'unknown'} of 100`}>
        <i style={{ width: `${Math.min(100, Math.max(0, v))}%` }} />
      </div>
    </div>
  )
}
