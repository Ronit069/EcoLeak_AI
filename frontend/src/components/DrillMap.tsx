import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import type { MockDataset, HotspotDetectionResult, ActivityData } from '../lib/contracts'
import { fmtKg } from '../lib/format'

type Level = 'facility' | 'process' | 'activity'
const SEV_COLOR: Record<string, string> = {
  CRITICAL: '#B3261E', HIGH: '#C2570B', MODERATE: '#8A6D00', LOW: '#3A7D44'
}

// Module N Carbon Leak Map — D3 drill-down: facility → process (hotspots) → activity.
// Built against mock_hotspot_output.json + mock_dataset.json; N2 links are [] in Phase 1.
export function DrillMap({
  dataset, hotspots
}: { dataset: MockDataset; hotspots: HotspotDetectionResult }) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [level, setLevel] = useState<Level>('facility')
  const [processId, setProcessId] = useState<string | null>(null)
  const selProcessId = processId ?? null
  const facility = dataset.facilities[0]
  const period = dataset.reporting_periods[0]
  const byProcess = new Map((hotspots.hotspots ?? []).map(h => [h.process_id, h]))
  const useSel = (id: string | null) => setProcessId(id)

  useEffect(() => {
    if (!svgRef.current) return
    const w = svgRef.current.clientWidth || 800
    const h = level === 'facility' ? 120 : 200
    const svg = d3.select(svgRef.current)
      .attr('viewBox', `0 0 ${w} ${h}`)
      .attr('aria-label', 'Carbon leak map drill-down')
      .attr('role', 'img')
    svg.selectAll('*').remove()

    if (level === 'facility') {
      // One facility node sized by total; drill label hints process view.
      const total = hotspots.total_emissions_kgco2e
      svg.append('rect')
        .attr('x', w / 2 - 90).attr('y', 12).attr('width', 180).attr('height', 84)
        .attr('rx', 10).attr('fill', '#211F1B')
        .style('cursor', 'pointer')
        .on('click', () => setLevel('process'))
      svg.append('text').attr('x', w / 2).attr('y', 38).attr('text-anchor', 'middle')
        .attr('fill', '#F5F1E6').style('font', '700 14px var(--font)')
        .text(facility.name)
      svg.append('text').attr('x', w / 2).attr('y', 58).attr('text-anchor', 'middle')
        .attr('fill', '#CFC7B4').style('font', '11px var(--mono)')
        .text(`${fmtKg(total)} · ${period.period_type} ${period.start_date}→${period.end_date}`)
      svg.append('text').attr('x', w / 2).attr('y', 78).attr('text-anchor', 'middle')
        .attr('fill', '#CFC7B4').style('font', '10px var(--font)')
        .text('click to drill into process hotspots →')
      return
    }

    if (level === 'process') {
      const items = hotspots.hotspots
      const x = d3.scaleBand().domain(items.map(h => h.id)).range([8, w - 8]).padding(0.18)
      const y = d3.scaleLinear().domain([0, d3.max(items.map(h => h.emissions_kgco2e)) ?? 1]).range([h - 30, 8])
      const tip = svg.append('g').style('pointer-events', 'none').style('opacity', 0)
      svg.selectAll('rect').data(items).join('rect')
        .attr('x', d => x(d.id)!).attr('width', x.bandwidth())
        .attr('y', d => y(d.emissions_kgco2e)).attr('height', d => y(0) - y(d.emissions_kgco2e))
        .attr('rx', 6).attr('fill', d => SEV_COLOR[d.severity] ?? '#3A7D44')
        .style('cursor', 'pointer')
        .on('click', (_e, d) => { useSel(d.process_id ?? null); setLevel('activity') })
        .on('mouseover', (_e, d) => {
          tip.style('opacity', 1)
          tip.selectAll('*').remove()
          tip.append('text').attr('x', 10).attr('y', -6).attr('fill', '#1E2328')
            .style('font', '12px var(--mono)')
            .text(`${d.process_name} · ${d.severity} · ${fmtKg(d.emissions_kgco2e)}`)
        })
        .on('mousemove', e => { const [mx] = d3.pointer(e); tip.attr('transform', `translate(${Math.min(mx, w - 220)},10)`) })
        .on('mouseout', () => tip.style('opacity', 0))
      svg.selectAll('.lbl').data(items).join('text').attr('class', 'lbl')
        .attr('x', d => x(d.id)! + x.bandwidth() / 2).attr('y', h - 10)
        .attr('text-anchor', 'middle').attr('fill', '#4A473F').style('font', '10px var(--font)')
        .style('pointer-events', 'none')
        .text(d => (d.process_name ?? '').slice(0, 10))
      return
    }

    // activity level for a process
    const acts: ActivityData[] = dataset.activity_data.filter(a => a.process_id === selProcessId)
    svg.append('text').attr('x', 8).attr('y', 16).attr('fill', '#4A473F').style('font', '700 12px var(--font)')
      .style('pointer-events', 'none')
      .text(`Activities under ${byProcess.get(selProcessId ?? '')?.process_name ?? 'process'} (${acts.length})`)
    const rows = acts.slice(0, 8)
    if (rows.length === 0) {
      svg.append('text').attr('x', 8).attr('y', 44).attr('fill', '#6B675E').style('font', '11px var(--font)')
        .style('pointer-events', 'none')
        .text('No activity records in mock for this process.')
      return
    }
    const max = d3.max(rows.map(a => Number(a.original_value ?? 0))) ?? 1
    const x = d3.scaleLinear().domain([0, max]).range([0, w - 140])
    rows.forEach((a, i) => {
      const yy = 40 + i * 24
      svg.append('text').attr('x', 8).attr('y', yy).attr('fill', '#1E2328').style('font', '11px var(--font)')
        .style('pointer-events', 'none')
        .text((a.activity_subcategory ?? '').slice(0, 24))
      svg.append('rect').attr('x', 132).attr('y', yy - 10).attr('width', x(Number(a.original_value ?? 0))).attr('height', 12)
        .attr('rx', 3).attr('fill', '#C2570B').attr('fill-opacity', 0.75)
      svg.append('text').attr('x', w - 8).attr('y', yy).attr('text-anchor', 'end').attr('fill', '#4A473F')
        .style('font', '10px var(--mono)').style('pointer-events', 'none')
        .text(`${a.original_value} ${a.original_unit}`)
    })
  }, [level, selProcessId, dataset, hotspots])

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }} aria-live="polite">
        {level !== 'facility' && (
          <button className="btn btn-ghost" type="button" style={{ padding: '5px 10px', fontSize: '.8rem' }} onClick={() => setLevel('facility')}>Facility</button>
        )}
        {level === 'activity' && (
          <button className="btn btn-ghost" type="button" style={{ padding: '5px 10px', fontSize: '.8rem' }} onClick={() => setLevel('process')}>Processes</button>
        )}
        <span className="mono" style={{ fontSize: '.8rem', color: 'var(--legend)' }}>
          {level === 'facility' ? 'facility' : level === 'process' ? 'facility → process' : 'facility → process → activity'}
        </span>
      </div>
      <svg ref={svgRef} style={{ width: '100%', minHeight: 120, display: 'block' }} />
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 6 }} aria-label="Severity legend">
        {Object.entries(SEV_COLOR).map(([s, c]) => (
          <span key={s} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '.76rem', color: 'var(--legend-ink)' }}>
            <span style={{ width: 10, height: 10, borderRadius: 3, background: c }} aria-hidden="true" />{s}
          </span>
        ))}
      </div>
    </div>
  )
}