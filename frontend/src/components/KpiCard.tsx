// Premium KPI card with count-up and micro sparkline.
import { useEffect, useRef, useState, type ReactNode } from 'react'

export interface KpiProps {
  label: string
  value: number | null
  format: (v: number | null) => string
  unit?: string
  delta?: string
  deltaDir?: 'up' | 'down' | 'flat'
  accent?: string
  spark?: number[]
  foot?: ReactNode
}

export function KpiCard({ label, value, format, unit, delta, deltaDir = 'flat', accent = 'var(--cyan)', spark, foot }: KpiProps) {
  const animated = useCountUp(value)
  return (
    <div className="kpi" style={{ ['--k-accent' as string]: accent }}>
      <div className="k-label">{label}</div>
      <div className="k-value">{format(animated)}{unit ? <span className="u">{unit}</span> : null}</div>
      {(delta || foot) ? (
        <div className="k-foot">
          {delta ? <span className={`delta ${deltaDir}`}>{delta}</span> : null}
          {foot}
        </div>
      ) : null}
      {spark && spark.length ? (
        <div className="spark" aria-hidden="true">
          {spark.map((s, i) => <i key={i} style={{ height: `${Math.max(12, Math.min(100, s))}%` }} />)}
        </div>
      ) : null}
    </div>
  )
}

function useCountUp(target: number | null, duration = 750): number | null {
  const [v, setV] = useState<number | null>(target)
  const fromRef = useRef(0)
  useEffect(() => {
    if (target === null || !Number.isFinite(target)) { setV(target); return }
    let raf = 0
    const start = performance.now()
    const from = target === 0 ? 0 : fromRef.current
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3)
      setV(from + (target - from) * eased)
      if (t < 1) raf = requestAnimationFrame(tick)
      else fromRef.current = target
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])
  return v
}
