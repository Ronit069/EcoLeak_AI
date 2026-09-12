import { useState } from 'react'
import { usePhase1Data, Loading } from './Dashboard'
import { SeverityBadge } from '../components/badges'
import { fmtKg, fmtPct } from '../lib/format'
import type { HotspotSeverity } from '../lib/contracts'

// Module B — Process Mapper UI (B1–B5).
// Visual flow builder: nodes carry energy source, fuel, material input, water,
// output, waste, operating hours. carbon_impact_level is a Phase 1 stub
// ("Low" default, upgraded from the hotspot mock where a process matches).
// Clicking a node opens the hotspot detail panel (mock_hotspot_output.json).
// Sequence arrows are implicit (Phase 2 owns the Sankey/links editor).

interface DraftExtras {
  energy_source: string; fuel: string; material_input: string; water: string
  output: string; waste: string; operating_hours: string
}

const EMPTY_EXTRAS: DraftExtras = {
  energy_source: '', fuel: '', material_input: '', water: '',
  output: '', waste: '', operating_hours: ''
}

export function ProcessesPage() {
  const { dataset, hotspots, processes, activities, error } = usePhase1Data()
  const [filter, setFilter] = useState('')
  const [local, setLocal] = useState<{ id: string; name: string; sequence_no: number; extras: DraftExtras }[]>([])
  const [name, setName] = useState('')
  const [seq, setSeq] = useState(7)
  const [extras, setExtras] = useState<DraftExtras>(EMPTY_EXTRAS)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  if (error) return <div className="notice"><b>Failed to load.</b> {error}</div>
  if (!dataset || !hotspots || !processes) return <Loading />

  const rows = [...processes]
    .sort((a, b) => (a.sequence_no ?? 99) - (b.sequence_no ?? 99))
    .filter(p => p.name.toLowerCase().includes(filter.toLowerCase()))

  const hotspotByProcess = new Map((hotspots.hotspots ?? []).map(h => [h.process_id, h]))
  const severityFor = (processId: string): HotspotSeverity =>
    hotspotByProcess.get(processId)?.severity ?? 'LOW'
  const selected = [...rows.map(r => ({ id: r.id, name: r.name, sequence_no: r.sequence_no ?? 0, extras: null as DraftExtras | null })),
    ...local.map(l => ({ ...l, extras: l.extras }))]
    .find(n => n.id === selectedId) ?? null
  const selectedHotspot = selected ? hotspotByProcess.get(selected.id) ?? null : null
  const selectedActivities = selected
    ? (activities ?? []).filter(a => a.process_id === selected.id)
    : []

  const setEx = (k: keyof DraftExtras) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setExtras({ ...extras, [k]: e.target.value })

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Process mapper</h1>
          <p>{processes.length} processes · click a node for hotspot detail · links editor ships in Phase 2</p>
        </div>
        <span className="provenance">B1–B5 · sequence_no &gt; 0 · carbon_impact_level stub</span>
      </div>

      <div className="panel panel-pad" style={{ marginBottom: 16 }}>
        <h2>Flow (sequence order)</h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'stretch' }} role="list" aria-label="Process flow">
          {rows.map((p, i) => {
            const sev = severityFor(p.id)
            const active = selectedId === p.id
            return (
              <span key={p.id} style={{ display: 'flex', alignItems: 'stretch', gap: 8 }}>
                <button
                  role="listitem"
                  onClick={() => setSelectedId(active ? null : p.id)}
                  aria-pressed={active}
                  className={`hotspot sev-${sev}`}
                  style={{ margin: 0, minWidth: 150, cursor: 'pointer' }}
                >
                  <span className="sev-rail" aria-hidden="true" />
                  <span>
                    <b className="mono">{p.sequence_no}. {p.name}</b>
                    <span style={{ display: 'block', marginTop: 4 }}><SeverityBadge severity={sev} /></span>
                    <small style={{ display: 'block', color: 'var(--legend)', marginTop: 2 }}>
                        impact: {hotspotByProcess.has(p.id) ? 'from hotspot' : 'stub Low'}
                    </small>
                  </span>
                </button>
                {i < rows.length - 1 && <span aria-hidden="true" style={{ alignSelf: 'center', color: 'var(--legend)' }}>→</span>}
              </span>
            )
          })}
        </div>
        {selected && (
          <div className="panel panel-pad" style={{ marginTop: 12, background: 'var(--ash-deep)' }} aria-live="polite">
            <h3>{selected.name} — hotspot detail</h3>
            {selectedHotspot ? (
              <>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                  <SeverityBadge severity={selectedHotspot.severity} />
                  <span className="mono" style={{ fontSize: '.82rem' }}>
                    {fmtKg(selectedHotspot.emissions_kgco2e)} · {fmtPct(selectedHotspot.contribution_percent)} · intensity {selectedHotspot.carbon_intensity ?? '—'} · score {selectedHotspot.hotspot_score ?? '—'}
                  </span>
                </div>
                {selectedHotspot.explanation && <p style={{ fontSize: '.86rem' }}>{selectedHotspot.explanation}</p>}
              </>
            ) : (
              <p style={{ fontSize: '.86rem' }}>No hotspot for this process in this period (e.g. Transportation) — explicit gap, not a zero.</p>
            )}
            <h4 style={{ margin: '10px 0 6px' }}>Activities ({selectedActivities.length})</h4>
            {selectedActivities.length === 0 ? (
              <p style={{ fontSize: '.84rem', color: 'var(--legend)' }}>No activity records for this process yet — add one in Data input (C1).</p>
            ) : (
              <ul style={{ fontSize: '.84rem', paddingLeft: 18, margin: 0 }}>
                {selectedActivities.map(a => (
                  <li key={a.id} className="mono">{a.activity_subcategory} · {String(a.original_value)} {a.original_unit}</li>
                ))}
              </ul>
            )}
            {selected.extras && (
              <p style={{ fontSize: '.8rem', color: 'var(--legend)' }}>
                Draft extras — energy: {selected.extras.energy_source || '—'} · fuel: {selected.extras.fuel || '—'} ·
                material: {selected.extras.material_input || '—'} · water: {selected.extras.water || '—'} ·
                output: {selected.extras.output || '—'} · waste: {selected.extras.waste || '—'} ·
                hours: {selected.extras.operating_hours || '—'}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="split">
        <div className="panel panel-pad">
          <div className="field">
            <label htmlFor="proc-filter">Filter processes (scales past 100)</label>
            <input id="proc-filter" value={filter} onChange={e => setFilter(e.target.value)} placeholder="Dyeing, Boiler…" />
          </div>
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Seq</th><th>Process</th><th>Code</th><th>Impact</th><th>Status</th></tr></thead>
              <tbody>
                {rows.map(p => (
                  <tr key={p.id}>
                    <td className="mono">{p.sequence_no}</td>
                    <td><b>{p.name}</b><br /><small style={{ color: 'var(--legend)' }}>{p.description ?? p.process_category ?? ''}</small></td>
                    <td className="mono">{p.process_code ?? '—'}</td>
                    <td><SeverityBadge severity={severityFor(p.id)} /></td>
                    <td>{p.active ? 'Active' : 'Inactive'}</td>
                  </tr>
                ))}
                {local.map(p => (
                  <tr key={p.id}><td className="mono">{p.sequence_no}</td><td><b>{p.name}</b> <small>(draft)</small></td><td className="mono">—</td><td><SeverityBadge severity="LOW" /></td><td>Draft</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ fontSize: '.8rem', color: 'var(--legend)' }}>
            Deleting a process with calculations soft-deletes only (B5). Source–target self-loops are rejected by contract.
          </p>
        </div>
        <form
          className="panel panel-pad"
          onSubmit={e => {
            e.preventDefault()
            if (!name.trim() || seq <= 0) return
            setLocal(l => [...l, { id: `draft-${Date.now()}`, name: name.trim(), sequence_no: seq, extras: { ...extras } }])
            setName(''); setSeq(rows.length + local.length + 1); setExtras(EMPTY_EXTRAS)
          }}
        >
          <h2>Add process node (B1)</h2>
          <div className="field">
            <label htmlFor="proc-name">Process name</label>
            <input id="proc-name" value={name} onChange={e => setName(e.target.value)} required maxLength={150} placeholder="Stenter, ETP…" />
            {name && processes.some(p => p.name.toLowerCase() === name.trim().toLowerCase()) && (
              <span className="field-error">Duplicate name — business rule rejects this on the API.</span>
            )}
          </div>
          <div className="field">
            <label htmlFor="proc-seq">Sequence no (must be &gt; 0)</label>
            <input id="proc-seq" type="number" min={1} value={seq} onChange={e => setSeq(Number(e.target.value))} />
          </div>
          <div className="form-grid">
            <div className="field"><label htmlFor="px-energy">Energy source</label><input id="px-energy" value={extras.energy_source} onChange={setEx('energy_source')} placeholder="Grid, steam…" /></div>
            <div className="field"><label htmlFor="px-fuel">Fuel</label><input id="px-fuel" value={extras.fuel} onChange={setEx('fuel')} placeholder="Natural gas, diesel…" /></div>
          </div>
          <div className="form-grid">
            <div className="field"><label htmlFor="px-mat">Material input</label><input id="px-mat" value={extras.material_input} onChange={setEx('material_input')} placeholder="Greige fabric…" /></div>
            <div className="field"><label htmlFor="px-water">Water</label><input id="px-water" value={extras.water} onChange={setEx('water')} placeholder="m³/batch…" /></div>
          </div>
          <div className="form-grid">
            <div className="field"><label htmlFor="px-out">Output</label><input id="px-out" value={extras.output} onChange={setEx('output')} placeholder="Dyed fabric…" /></div>
            <div className="field"><label htmlFor="px-waste">Waste</label><input id="px-waste" value={extras.waste} onChange={setEx('waste')} placeholder="Offcuts, effluent…" /></div>
          </div>
          <div className="field">
            <label htmlFor="px-hours">Operating hours</label>
            <input id="px-hours" value={extras.operating_hours} onChange={setEx('operating_hours')} placeholder="16 h/day…" />
            <small>carbon_impact_level stubs to Low until P3 supplies it; hotspot severity shown where a hotspot matches.</small>
          </div>
          <button className="btn btn-primary" type="submit">Add to map</button>
          <p style={{ fontSize: '.78rem', color: 'var(--legend)' }}>Live: POST /api/facilities/{'{id}'}/processes · 201 Process</p>
        </form>
      </div>
    </>
  )
}
