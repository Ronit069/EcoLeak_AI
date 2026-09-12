// Signature Carbon Leak Map: process network with deterministic carbon flow.
import { useMemo } from 'react'
import { Droplets, Factory, Flame, Recycle, Truck, Zap } from 'lucide-react'
import { fmtCo2e } from '../lib/format'
import type { Severity } from '../lib/types'

export interface NetNode {
  id: string
  name: string
  emissions: number | null
  contribution: number | null
  severity: Severity | null
  muted?: boolean
}

interface Props {
  nodes: NetNode[]
  selectedId: string | null
  onSelect: (id: string) => void
  onOpen?: (id: string) => void
  compact?: boolean
}

const SEV_COLOR: Record<Severity, string> = {
  LOW: '#10b981',
  MODERATE: '#f59e0b',
  HIGH: '#f97316',
  CRITICAL: '#f43f5e',
}

const SEV_BG: Record<Severity, string> = {
  LOW: 'rgba(16, 185, 129, 0.12)',
  MODERATE: 'rgba(245, 158, 11, 0.12)',
  HIGH: 'rgba(249, 115, 22, 0.12)',
  CRITICAL: 'rgba(244, 63, 94, 0.15)',
}

function iconFor(name: string) {
  const n = name.toLowerCase()
  if (n.includes('boil') || n.includes('furnace') || n.includes('heat')) return Flame
  if (n.includes('dry') || n.includes('electric') || n.includes('power')) return Zap
  if (n.includes('dye') || n.includes('water') || n.includes('wash')) return Droplets
  if (n.includes('pack') || n.includes('waste') || n.includes('recycl') || n.includes('finish')) return Recycle
  if (n.includes('trans') || n.includes('logist')) return Truck
  return Factory
}

export function ProcessNetwork({ nodes, selectedId, onSelect, onOpen, compact = false }: Props) {
  const cols = 3
  const NODE_W = compact ? 214 : 274
  const NODE_H = compact ? 74 : 96
  const gapX = compact ? 34 : 56
  const gapY = compact ? 28 : 64
  const W = compact ? 760 : 980
  const H = compact ? 220 : 330
  const startX = (W - (cols * NODE_W + (cols - 1) * gapX)) / 2
  const startY = (H - (2 * NODE_H + gapY)) / 2

  const placed = useMemo(() => {
    const list = [...nodes].slice(0, 6)
    // Row 0 left→right, row 1 right→left (serpentine) for continuous flow
    return list.map((n, i) => {
      const row = Math.floor(i / cols)
      const col = row % 2 === 0 ? i % cols : cols - 1 - (i % cols)
      return { ...n, x: startX + col * (NODE_W + gapX), y: startY + row * (NODE_H + gapY), i }
    })
  }, [nodes, startX, gapX, NODE_H, gapY, startY, NODE_W])

  const edges = useMemo(() => {
    const out: Array<{ a: typeof placed[number]; b: typeof placed[number]; loop?: string }> = []
    for (let i = 0; i < placed.length - 1; i++) out.push({ a: placed[i], b: placed[i + 1] })
    // Branching closed-loop circularity links
    if (placed.length >= 5) out.push({ a: placed[0], b: placed[4], loop: 'water recirculation loop' })
    if (placed.length >= 6) out.push({ a: placed[2], b: placed[5], loop: 'flue-gas heat recovery' })
    return out
  }, [placed])

  const anchor = (n: typeof placed[number], toward: typeof placed[number]) => {
    const ax = n.x + NODE_W / 2, ay = n.y + NODE_H / 2
    const bx = toward.x + NODE_W / 2, by = toward.y + NODE_H / 2
    const dx = bx - ax, dy = by - ay
    const ex = NODE_W / 2 + 4, ey = NODE_H / 2 + 4
    const t = Math.min(ex / Math.abs(dx || 1), ey / Math.abs(dy || 1))
    return { x1: ax + dx * t, y1: ay + dy * t, x2: bx - dx * t, y2: by - dy * t, ax, ay, bx, by }
  }

  return (
    <svg className="network" viewBox={`0 0 ${W} ${H}`} role="group" aria-label="Process carbon leak network">
      <defs>
        <linearGradient id="node-bg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#141c2b" />
          <stop offset="100%" stopColor="#0b1019" />
        </linearGradient>
        <linearGradient id="node-bg-selected" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#18273d" />
          <stop offset="100%" stopColor="#0d1726" />
        </linearGradient>
        <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor="#06b6d4" floodOpacity="0.6" />
        </filter>
        <filter id="glow-coral" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor="#f43f5e" floodOpacity="0.4" />
        </filter>
        <marker id="net-arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path className="arrowhead" d="M0,0 L6,3 L0,6 Z" fill="rgba(6, 182, 212, 0.7)" />
        </marker>
        <marker id="net-arrow-hot" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path className="arrowhead" d="M0,0 L6,3 L0,6 Z" fill="#f43f5e" />
        </marker>
      </defs>

      {/* Energy & Carbon Piping Edges */}
      {edges.map((e, idx) => {
        const { x1, y1, x2, y2 } = anchor(e.a, e.b)
        const hot = e.a.severity === 'CRITICAL' || e.b.severity === 'CRITICAL'
        const pathId = `edge-${compact ? 'c' : 'f'}-${idx}`
        return (
          <g key={pathId}>
            <path
              id={pathId}
              className={`edge ${hot ? 'hot' : ''}`}
              d={`M ${x1} ${y1} L ${x2} ${y2}`}
              stroke={hot ? 'rgba(244, 63, 94, 0.55)' : e.loop ? 'rgba(6, 182, 212, 0.35)' : 'rgba(255, 255, 255, 0.16)'}
              strokeWidth={hot ? 2 : 1.5}
              strokeDasharray={e.loop ? '4 4' : undefined}
              fill="none"
              markerEnd={hot ? 'url(#net-arrow-hot)' : 'url(#net-arrow)'}
            />
            {/* Animated Stream Particles */}
            {[0, 1].map((p) => (
              <circle
                key={p}
                className="particle"
                r={hot ? 3 : 2}
                fill={hot ? '#f43f5e' : '#06b6d4'}
                filter={hot ? 'url(#glow-coral)' : 'url(#glow-cyan)'}
              >
                <animateMotion dur={`${2.8 + p * 0.7}s`} repeatCount="indefinite" begin={`${p * 0.9}s`}>
                  <mpath href={`#${pathId}`} />
                </animateMotion>
              </circle>
            ))}
            {e.loop && !compact ? (
              <g>
                <rect
                  x={(x1 + x2) / 2 - 60}
                  y={(y1 + y2) / 2 - 14}
                  width={120}
                  height={16}
                  rx={4}
                  fill="rgba(6, 10, 18, 0.85)"
                  stroke="rgba(6, 182, 212, 0.25)"
                />
                <text
                  x={(x1 + x2) / 2}
                  y={(y1 + y2) / 2 - 3}
                  textAnchor="middle"
                  fill="#06b6d4"
                  style={{ fontFamily: 'var(--mono)', fontSize: 9.5, letterSpacing: '0.04em', fontWeight: 600 }}
                >
                  {e.loop}
                </text>
              </g>
            ) : null}
            <title>{`${e.a.name} → ${e.b.name}${e.loop ? ` (${e.loop})` : ''}`}</title>
          </g>
        )
      })}

      {/* Process Nodes */}
      {placed.map((n) => {
        const Icon = iconFor(n.name)
        const sel = n.id === selectedId
        const dim = selectedId !== null && !sel
        const sev = n.severity ?? 'LOW'
        const color = n.muted ? '#64748b' : SEV_COLOR[sev]
        const isCritical = sev === 'CRITICAL' && !n.muted

        return (
          <g
            key={n.id}
            tabIndex={0}
            role="button"
            aria-label={`${n.name} ${sev} ${n.contribution?.toFixed(1) ?? '—'} percent`}
            onClick={() => onSelect(n.id)}
            onDoubleClick={() => onOpen?.(n.id)}
            onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onSelect(n.id) } }}
            style={{
              cursor: 'pointer',
              opacity: dim ? 0.38 : 1,
              transition: 'opacity 140ms ease, transform 140ms ease',
            }}
          >
            {/* Card Background */}
            <rect
              x={n.x}
              y={n.y}
              width={NODE_W}
              height={NODE_H}
              rx={8}
              fill={sel ? 'url(#node-bg-selected)' : 'url(#node-bg)'}
              stroke={sel ? '#06b6d4' : isCritical ? 'rgba(244, 63, 94, 0.5)' : 'rgba(255, 255, 255, 0.1)'}
              strokeWidth={sel ? 2 : 1}
              filter={sel ? 'url(#glow-cyan)' : isCritical ? 'url(#glow-coral)' : undefined}
            />

            {/* Severity edge strip */}
            <rect x={n.x} y={n.y + 6} width={4} height={NODE_H - 12} fill={color} rx={2} />

            <foreignObject x={n.x + 12} y={n.y + 8} width={NODE_W - 20} height={NODE_H - 14}>
              <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '100%' }}>
                {/* Header row: Icon, Name, Severity Badge */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                    <div style={{
                      width: compact ? 18 : 22,
                      height: compact ? 18 : 22,
                      borderRadius: 4,
                      background: 'rgba(255, 255, 255, 0.05)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}>
                      <Icon size={compact ? 12 : 13} style={{ color: sel ? '#22d3ee' : '#94a3b8' }} />
                    </div>
                    <span style={{
                      fontWeight: 700,
                      fontSize: compact ? '12px' : '13px',
                      color: sel ? '#ffffff' : '#f1f5f9',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}>
                      {n.name}
                    </span>
                  </div>

                  {!n.muted ? (
                    <span style={{
                      fontFamily: 'var(--mono)',
                      fontSize: compact ? '9.5px' : '10px',
                      fontWeight: 700,
                      color,
                      background: SEV_BG[sev],
                      padding: '1px 6px',
                      borderRadius: 4,
                      border: `1px solid ${color}40`,
                      flexShrink: 0
                    }}>
                      {sev}
                    </span>
                  ) : (
                    <span style={{ fontFamily: 'var(--mono)', fontSize: '9px', color: '#64748b' }}>NO DATA</span>
                  )}
                </div>

                {/* Metrics row */}
                <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginTop: 2 }}>
                  <div>
                    <div className="num" style={{
                      fontSize: compact ? '14px' : '17px',
                      fontWeight: 700,
                      color: n.muted ? '#64748b' : '#f8fafc',
                      letterSpacing: '-0.02em',
                      lineHeight: 1.1
                    }}>
                      {n.muted ? '—' : fmtCo2e(n.emissions)}
                    </div>
                    {!compact ? (
                      <div style={{ fontFamily: 'var(--mono)', fontSize: '10px', color: '#64748b', marginTop: 2 }}>
                        SCOPE 1+2 OPERATIONAL
                      </div>
                    ) : null}
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{
                      fontFamily: 'var(--mono)',
                      fontSize: compact ? '12px' : '13.5px',
                      fontWeight: 700,
                      color: isCritical ? '#f43f5e' : '#cbd5e1'
                    }}>
                      {n.contribution === null ? '—' : `${n.contribution.toFixed(1)}%`}
                    </div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: '9.5px', color: '#64748b' }}>
                      SHARE
                    </div>
                  </div>
                </div>
              </div>
            </foreignObject>

            {/* Critical Hotspot Animated Beacon */}
            {isCritical ? (
              <g>
                <circle cx={n.x + NODE_W - 8} cy={n.y + 8} r={3} fill="#f43f5e">
                  <animate attributeName="r" values="2.5;5;2.5" dur="1.8s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="1;0.3;1" dur="1.8s" repeatCount="indefinite" />
                </circle>
              </g>
            ) : null}
          </g>
        )
      })}

      {placed.length === 0 ? (
        <text x={W / 2} y={H / 2} textAnchor="middle" fill="#64748b" style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>
          No process map available — configure processes in Factory Profile.
        </text>
      ) : null}
    </svg>
  )
}
