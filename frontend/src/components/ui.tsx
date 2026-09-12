// EcoLeak AI — instrument building blocks (no decorative layer).
import type { ReactNode } from 'react'
import type { Severity, ValidationSeverity } from '../lib/types'
import { DASH, fmtNumber, fmtPct, isNil, num } from '../lib/format'

export function Label({ children }: { children: ReactNode }) {
  return <span className="label">{children}</span>
}

export function Badge({ children, className = '', title }: { children: ReactNode; className?: string; title?: string }) {
  return <span className={`badge ${className}`} title={title}>{children}</span>
}

export function SeverityBadge({ severity }: { severity: Severity | null | undefined }) {
  if (!severity) return <span className="faint">—</span>
  return (
    <span className={`badge sev sev-${severity}`}>
      <span className={`sev-dot dot-${severity}`} aria-hidden="true" />
      {severity}
    </span>
  )
}

export function ValidationBadge({ severity }: { severity: ValidationSeverity }) {
  const cls = severity === 'ERROR' ? 'sev-CRITICAL'
    : severity === 'WARNING' ? 'sev-MODERATE'
      : severity === 'CONFIRMATION_REQUIRED' ? 'sev-HIGH' : 'stamp-UNAVAILABLE'
  return <span className={`badge ${cls}`}>{severity.replace('_', ' ')}</span>
}

export function SourceStamp({ source }: { source: 'live' | 'mock' | null }) {
  if (source === 'live') return <Badge className="source-live">LIVE ●</Badge>
  if (source === 'mock') return <Badge className="source-mock">DEMO ○</Badge>
  return null
}

export function StatusStamp({ status }: { status: string | null | undefined }) {
  const s = (status ?? 'UNAVAILABLE').toUpperCase()
  return <Badge className={`stamp-${s}`}>{s}</Badge>
}

export function MetricBlock({ items }: { items: Array<{ label: string; value: ReactNode; unit?: string; sub?: ReactNode }> }) {
  return (
    <div className="metrics">
      {items.map((it) => (
        <div className="metric" key={it.label}>
          <Label>{it.label}</Label>
          <div className="v">{it.value}{it.unit ? <span className="u">{it.unit}</span> : null}</div>
          {it.sub ? <div className="tiny faint">{it.sub}</div> : null}
        </div>
      ))}
    </div>
  )
}

export function ScopeBars({ items }: { items: Array<{ scope: 'SCOPE_1' | 'SCOPE_2' | 'SCOPE_3'; value: unknown }> }) {
  const parsed = items.map((i) => ({ ...i, n: num(i.value) }))
  const total = parsed.reduce((s, i) => s + (i.n ?? 0), 0)
  const cls = { SCOPE_1: 's1', SCOPE_2: 's2', SCOPE_3: 's3' } as const
  return (
    <div>
      {parsed.map((i) => {
        const pct = total > 0 && i.n !== null ? (i.n / total) * 100 : null
        return (
          <div className="scopebar" key={i.scope}>
            <span className="label">{i.scope.replace('_', ' ')}</span>
            <div className={`bar ${cls[i.scope]}`}>
              <span style={{ width: `${Math.max(0, Math.min(100, pct ?? 0))}%` }} />
            </div>
            <span className="num small">{isNil(i.value) ? DASH : fmtNumber(i.value, 0)}</span>
            <span className="num tiny faint">{pct === null ? DASH : fmtPct(pct, 0)}</span>
          </div>
        )
      })}
    </div>
  )
}

export function Gauge({ label, value, max = 100 }: { label: string; value: unknown; max?: number }) {
  const n = num(value)
  const pct = n === null ? 0 : Math.max(0, Math.min(100, (n / max) * 100))
  return (
    <div className="gauge">
      <Label>{label}</Label>
      <div className="track"><span style={{ width: `${pct}%` }} /></div>
      <span className="num small">{isNil(value) ? DASH : fmtNumber(value, 1)}</span>
    </div>
  )
}

export function ScoreBars({ scores }: { scores: Array<{ label: string; value: unknown }> }) {
  return (
    <div className="score-bars">
      {scores.map((s) => {
        const n = num(s.value)
        return (
          <div className="row" key={s.label}>
            <span className="label">{s.label}</span>
            <div className="track"><span style={{ width: `${n === null ? 0 : Math.max(0, Math.min(100, n))}%` }} /></div>
            <span className="num tiny">{isNil(s.value) ? DASH : fmtNumber(s.value, 0)}</span>
          </div>
        )
      })}
    </div>
  )
}

export function Banner({ kind = 'info', title, children }: { kind?: 'info' | 'warning' | 'error' | 'lock'; title?: string; children?: ReactNode }) {
  return (
    <div className={`banner ${kind}`} role={kind === 'error' ? 'alert' : undefined}>
      <div>
        {title ? <div><strong>{title}</strong></div> : null}
        {children}
      </div>
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>
}

export function Loading({ what = 'data' }: { what?: string }) {
  return <div className="loading">LOADING {what.toUpperCase()}…</div>
}

export function ErrorState({ error }: { error: Error }) {
  return <Banner kind="error" title={error.message}>{'\u00a0'}</Banner>
}

export function SectionHead({ title, right }: { title: string; right?: ReactNode }) {
  return (
    <div className="section-head">
      <Label>{title}</Label>
      <div className="spacer" />
      {right}
    </div>
  )
}
