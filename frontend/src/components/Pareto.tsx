import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { HotspotOutputItem } from '../lib/contracts'

// Pareto chart (Module N): bars = contribution %, line = cumulative share.
// Null contribution (real API can omit it) renders an explicit "unavailable"
// label instead of a misleading bar (D1) — and never a 0-width bar.
export function Pareto({ items }: { items: HotspotOutputItem[] }) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!svgRef.current) return
    const w = svgRef.current.clientWidth || 760
    const h = 220
    const m = { top: 18, right: 40, bottom: 42, left: 44 }
    const svg = d3.select(svgRef.current).attr('viewBox', `0 0 ${w} ${h}`)
    svg.selectAll('*').remove()

    const available = items.filter(i => i.contribution_percent != null)
    if (available.length === 0) {
      svg.append('text').attr('x', 12).attr('y', 40)
        .attr('fill', '#6B675E').style('font', '13px var(--font)')
        .text('Contribution data unavailable — no bars rendered.')
      return
    }
    const sorted = [...available].sort((a, b) => (b.contribution_percent ?? 0) - (a.contribution_percent ?? 0))
    const total = d3.sum(sorted, d => d.contribution_percent ?? 0) || 1
    let cum = 0
    const cumul = sorted.map(d => { cum += (d.contribution_percent ?? 0) / total * 100; return cum })

    const x = d3.scaleBand().domain(sorted.map(d => d.process_name ?? '?')).range([m.left, w - m.right]).padding(0.25)
    const y = d3.scaleLinear().domain([0, 100]).range([h - m.bottom, m.top])
    const y2 = d3.scaleLinear().domain([0, 100]).range([h - m.bottom, m.top])

    svg.append('g').attr('transform', `translate(0,${h - m.bottom})`)
      .call(d3.axisBottom(x).tickSize(0))
      .selectAll('text').attr('dy', '1em').style('font-size', '10px')
    svg.append('g').attr('transform', `translate(${m.left},0)`)
      .call(d3.axisLeft(y).ticks(5).tickFormat(d => `${d}%`))
      .selectAll('text').style('font-size', '10px')

    svg.selectAll('.bar').data(sorted).join('rect')
      .attr('class', 'bar')
      .attr('x', d => x(d.process_name ?? '?')!)
      .attr('width', x.bandwidth())
      .attr('y', d => y(d.contribution_percent ?? 0))
      .attr('height', d => y(0) - y(d.contribution_percent ?? 0))
      .attr('rx', 4)
      .attr('fill', '#2A2721')
      .append('title')
      .text(d => `${d.process_name}: ${d.contribution_percent?.toFixed(2)}%`)

    const line = d3.line<number>()
      .x((_, i) => (x(sorted[i].process_name ?? '?') ?? 0) + x.bandwidth() / 2)
      .y(d => y2(d))
    svg.append('path')
      .datum(cumul)
      .attr('fill', 'none').attr('stroke', 'var(--accent)').attr('stroke-width', 2)
      .attr('d', line)
    svg.selectAll('.dot').data(cumul).join('circle')
      .attr('cx', (_, i) => (x(sorted[i].process_name ?? '?') ?? 0) + x.bandwidth() / 2)
      .attr('cy', d => y2(d)).attr('r', 3).attr('fill', 'var(--accent)')

    svg.append('text').attr('x', w - m.right - 4).attr('y', m.top - 4)
      .attr('text-anchor', 'end').attr('fill', 'var(--legend)').style('font', '10px var(--font)')
      .text('— cumulative % (right axis)')
  }, [items])

  return (
    <div style={{ marginTop: 12 }} aria-label="Pareto chart: hotspot contribution share">
      <svg ref={svgRef} style={{ width: '100%', height: '220px', display: 'block' }} role="img"
        aria-label="Pareto of hotspot contributions with cumulative line" />
      <table className="data" style={{ width: '100%', marginTop: 4, fontSize: '.78rem' }}>
        <thead><tr><th>Process</th><th className="n">Contribution</th><th className="n">Cumulative</th></tr></thead>
        <tbody>
          {items.map(i => {
            const idx = items.indexOf(i)
            const share = i.contribution_percent ?? items.filter(x => x.contribution_percent != null)
              .sort((a, b) => (b.contribution_percent ?? 0) - (a.contribution_percent ?? 0)).indexOf(i)
            return (
              <tr key={i.id}>
                <td>{i.process_name ?? 'Unassigned'}</td>
                <td className="n mono">{i.contribution_percent != null ? `${i.contribution_percent.toFixed(2)}%` : 'unavailable'}</td>
                <td className="n mono">{share >= 0 ? cumLabel(items, i, idx) : '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function cumLabel(items: HotspotOutputItem[], target: HotspotOutputItem, _idx: number): string {
  const available = items.filter(i => i.contribution_percent != null)
    .sort((a, b) => (b.contribution_percent ?? 0) - (a.contribution_percent ?? 0))
  const total = d3.sum(items, d => d.contribution_percent ?? 0) || 1
  let cum = 0
  for (const item of available) {
    cum += (item.contribution_percent ?? 0) / total * 100
    if (item.id === target.id) return `${cum.toFixed(1)}%`
  }
  return '—'
}