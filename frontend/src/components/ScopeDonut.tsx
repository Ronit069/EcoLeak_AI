import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

// Scope donut (Module N): consumes N1 scope_breakdown directly. Accessible:
// each segment has a label + value in the legend and a screen-reader table;
// color is never the only indicator (scope names + percentages are text).
export function ScopeDonut({
  breakdown, total,
}: { breakdown: Record<string, number> | null | undefined; total: number }) {
  const svgRef = useRef<SVGSVGElement>(null)
  const scopes = breakdown != null
    ? Object.entries(breakdown).filter(([, v]) => v != null && v > 0)
    : []

  useEffect(() => {
    if (!svgRef.current || scopes.length === 0) return
    const size = 150, r = 60, ir = 34
    const svg = d3.select(svgRef.current)
      .attr('viewBox', `0 0 ${size} ${size}`)
      .attr('role', 'img')
      .attr('aria-label', 'Scope donut: emissions share by scope')
    svg.selectAll('*').remove()
    const pie = d3.pie<[string, number]>().value(d => d[1]).sort(null)
    const arc = d3.arc<d3.PieArcDatum<[string, number]>>().innerRadius(ir).outerRadius(r)
    const colors: Record<string, string> = {
      SCOPE_1: '#B3261E', SCOPE_2: '#E4572E', SCOPE_3: '#C2570B',
      UNKNOWN: '#7A766F',
    }
    svg.append('g').attr('transform', `translate(${size / 2},${size / 2})`)
      .selectAll('path').data(pie(scopes)).join('path')
      .attr('d', arc as never)
      .attr('fill', d => colors[d.data[0]] ?? colors.UNKNOWN)
      .attr('stroke', '#fff').attr('stroke-width', 2)
      .append('title').text(d => `${d.data[0]}: ${d.data[1].toLocaleString('en-IN')} kgCO2e`)
    svg.append('text').attr('x', size / 2).attr('y', size / 2 - 4)
      .attr('text-anchor', 'middle').style('font', '700 12px var(--font)').attr('fill', '#1E2328')
      .text(total.toLocaleString('en-IN'))
    svg.append('text').attr('x', size / 2).attr('y', size / 2 + 12)
      .attr('text-anchor', 'middle').style('font', '9px var(--legend)').attr('fill', '#6B675E')
      .text('kgCO₂e')
  }, [scopes, total])

  if (scopes.length === 0) {
    return <div className="notice" style={{ fontSize: '.82rem' }}>Scope breakdown unavailable — N1 not served or all scopes zero.</div>
  }
  const sum = scopes.reduce((a, [, v]) => a + v, 0) || 1
  return (
    <div aria-label="Scope donut">
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <svg ref={svgRef} style={{ width: 150, height: 150 }} />
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, fontSize: '.8rem', color: 'var(--ink)' }}>
          {scopes.map(([name, v]) => {
            const pct = (v / sum) * 100
            return (
              <li key={name} style={{ display: 'flex', gap: 8, alignItems: 'center', margin: '3px 0' }}>
                <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 3, background: ({ SCOPE_1: '#B3261E', SCOPE_2: '#E4572E', SCOPE_3: '#C2570B' } as Record<string, string>)[name] ?? '#7A766F' }} />
                <b>{name.replace('_', ' ')}</b>
                <span className="mono">{v.toLocaleString('en-IN')} kgCO₂e</span>
                <span className="mono">{pct.toFixed(1)}%</span>
              </li>
            )
          })}
        </ul>
      </div>
      <table className="data" style={{ width: '100%', marginTop: 6, fontSize: '.76rem' }}>
        <caption style={{ textAlign: 'left', fontSize: '.68rem', color: 'var(--legend)' }}>Scope breakdown (screen-reader table)</caption>
        <thead><tr><th>Scope</th><th className="n">kgCO₂e</th><th className="n">Share</th></tr></thead>
        <tbody>
          {scopes.map(([name, v]) => (
            <tr key={name}><td>{name}</td><td className="n mono">{v.toLocaleString('en-IN')}</td>
              <td className="n mono">{((v / sum) * 100).toFixed(1)}%</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}