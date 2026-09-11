import { useRef, useState } from 'react'
import { usePhase1Data, Loading } from './Dashboard'
import { activityInputSchema } from '../lib/zod'

interface PreviewRow {
  row: number
  data: Record<string, string>
  issues: { severity: 'ERROR' | 'WARNING' | 'INFO' | 'CONFIRMATION_REQUIRED'; code: string; message: string; field?: string }[]
}

// C4 client-side preview only — never parses server-side. Header validation mirrors
// Pandera checks; validation issues use the ValidationIssue[] shape from §23.
const EXPECTED_HEADERS = ['activity_subcategory', 'original_value', 'original_unit', 'activity_category']
const CATEGORIES = ['ELECTRICITY', 'FUEL', 'MATERIAL', 'WATER', 'TRANSPORT', 'WASTE', 'REFRIGERANT', 'STEAM', 'OTHER']
const UNITS = ['kWh', 'MWh', 'm3', 'L', 'kg', 'tonne', 't', 'km', 'pcs']

function parseCsv(text: string): string[][] {
  const rows: string[][] = []
  let cur: string[] = [], field = '', inQ = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (inQ) {
      if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++ } else inQ = false }
      else field += c
    } else if (c === '"') inQ = true
    else if (c === ',' || c === ';') { cur.push(field); field = '' }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++
      cur.push(field); field = ''
      rows.push(cur); cur = []
    } else field += c
  }
  if (field !== '' || cur.length) { cur.push(field); rows.push(cur) }
  return rows.filter(r => r.some(c => c.trim() !== ''))
}

function validateRow(rowIdx: number, data: Record<string, string>): PreviewRow['issues'] {
  const issues: PreviewRow['issues'] = []
  const sub = (data.activity_subcategory ?? '').trim()
  const val = Number(data.original_value)
  const unit = (data.original_unit ?? '').trim()
  const cat = (data.activity_category ?? '').trim().toUpperCase()
  if (!sub) issues.push({ severity: 'ERROR', code: 'MISSING_SUBCATEGORY', message: 'activity_subcategory is required', field: 'activity_subcategory' })
  if (data.original_value === undefined || data.original_value === '') issues.push({ severity: 'ERROR', code: 'MISSING_VALUE', message: 'original_value is required', field: 'original_value' })
  else if (Number.isNaN(val) || val < 0) issues.push({ severity: 'ERROR', code: 'INVALID_VALUE', message: 'original_value must be a non-negative number', field: 'original_value' })
  if (!UNITS.includes(unit.toLowerCase())) issues.push({ severity: 'WARNING', code: 'UNIT_NOT_ALLOWLISTED', message: `unit ${unit || '(blank)'} is not in the allow-list` })
  if (unit.toLowerCase() === 'tonne' && val > 1000) issues.push({ severity: 'CONFIRMATION_REQUIRED', code: 'MAGNITUDE_ANOMALY', message: 'tonne value looks like kg — confirm magnitude' })
  if (cat && !CATEGORIES.includes(cat)) issues.push({ severity: 'ERROR', code: 'INVALID_CATEGORY', message: `unknown activity_category ${cat}` })
  return issues
}

// Module C-frontend — Data Input forms (C1–C4, D1–D2). Zod mirrors Pydantic:
// non-negative values, unit allow-list hint, ESTIMATED caps confidence note.

export function DataInputPage() {
  const { dataset, error } = usePhase1Data()
  const [form, setForm] = useState({
    process_id: '', activity_category: 'ELECTRICITY', activity_subcategory: '',
    original_value: '', original_unit: 'kWh',
    data_source_type: 'MANUAL', measured_or_estimated: 'MEASURED', confidence_score: '85'
  })
  const [issues, setIssues] = useState<string[]>([])
  const [saved, setSaved] = useState<string[]>([])
  const fileRef = useRef<HTMLInputElement>(null)
  const [importRows, setImportRows] = useState<PreviewRow[]>([])
  const [importSummary, setImportSummary] = useState<string | null>(null)

  const handleFile = (file: File | undefined) => {
    setImportRows([]); setImportSummary(null)
    if (!file) return
    if (!/\.(csv|xlsx?)$/i.test(file.name)) {
      setImportSummary('File type rejected — .csv / .xlsx only (C4 file-size/type allow-list).')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setImportSummary('File too large (> 5 MB) — rejected by C4 allow-list.')
      return
    }
    if (file.name.toLowerCase().endsWith('.xlsx') || file.name.toLowerCase().endsWith('.xls')) {
      setImportSummary('XLSX preview needs the openpyxl/Pandera path on the backend (C4). Header check is deferred — client shows raw file metadata only.')
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      const text = String(reader.result ?? '')
      if (!text.trim()) { setImportSummary('Empty file rejected — no data rows.'); return }
      const grid = parseCsv(text)
      if (grid.length < 2) { setImportSummary('Corrupt / single-row file — no data rows to validate.'); return }
      const headers = grid[0].map(h => (h || '').trim())
      const missing = EXPECTED_HEADERS.filter(h => !headers.includes(h))
      setImportSummary(
        missing.length
          ? `Header validation failed — missing columns: ${missing.join(', ')}. Pandera (backend) will reject this.`
          : `${grid.length - 1} data rows · header OK · Pandera + MIME check still run on upload.`
      )
      const rows: PreviewRow[] = []
      for (let i = 1; i < grid.length; i++) {
        const vals = grid[i]
        const data: Record<string, string> = {}
        headers.forEach((h, j) => { data[h] = (vals[j] ?? '').trim() })
        rows.push({ row: i + 1, data, issues: validateRow(i + 1, data) })
      }
      setImportRows(rows)
    }
    reader.readAsText(file)
  }
  if (error) return <div className="notice"><b>Failed to load.</b> {error}</div>
  if (!dataset) return <Loading />

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Factory data capture</h1>
          <p>{dataset.activity_data.length} activity records in mock · kg↔tonne and m³ exercise the Pint path · diesel record is the litre case</p>
        </div>
        <span className="provenance">C1–C4 · D1 normalize · D2 quality 78.4</span>
      </div>
      <div className="split">
        <form
          className="panel panel-pad"
          onSubmit={e => {
            e.preventDefault()
            const parsed = activityInputSchema.safeParse({
              process_id: form.process_id,
              activity_category: form.activity_category,
              activity_subcategory: form.activity_subcategory,
              original_value: Number(form.original_value),
              original_unit: form.original_unit,
              data_source_type: form.data_source_type,
              measured_or_estimated: form.measured_or_estimated,
              confidence_score: form.confidence_score === '' ? null : Number(form.confidence_score)
            })
            if (!parsed.success) {
              setIssues(parsed.error.issues.map(i => `${i.path.join('.')}: ${i.message}`))
              return
            }
            const errs: string[] = []
            if (form.original_unit === 'tonne' && Number(form.original_value) > 1000)
              errs.push('Magnitude check: tonne value looks like kg — confirm unit (edge case C/D).')
            if (form.measured_or_estimated === 'ESTIMATED')
              errs.push('Note: ESTIMATED values ship with lower confidence and OCR-derived rows are flagged.')
            setIssues(errs)
            const proc = dataset.processes.find(p => p.id === form.process_id)?.name ?? 'process'
            setSaved(s => [`${form.activity_subcategory} · ${form.original_value} ${form.original_unit} → ${proc}`, ...s])
          }}
        >
          <h2>Log activity (C1)</h2>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="f-proc">Process</label>
              <select id="f-proc" value={form.process_id} onChange={e => setForm({ ...form, process_id: e.target.value })}>
                <option value="">Select…</option>
                {dataset.processes.map(p => <option key={p.id} value={p.id}>{p.sequence_no}. {p.name}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="f-cat">Category</label>
              <select id="f-cat" value={form.activity_category} onChange={e => setForm({ ...form, activity_category: e.target.value })}>
                {['ELECTRICITY','FUEL','MATERIAL','WATER','TRANSPORT','WASTE','REFRIGERANT','STEAM','OTHER'].map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="f-sub">Subcategory</label>
              <input id="f-sub" value={form.activity_subcategory} onChange={e => setForm({ ...form, activity_subcategory: e.target.value })} placeholder="Grid electricity, Natural gas…" maxLength={100} />
            </div>
            <div className="field">
              <label htmlFor="f-val">Original value (≥ 0)</label>
              <input id="f-val" type="number" min={0} step="any" value={form.original_value} onChange={e => setForm({ ...form, original_value: e.target.value })} placeholder="210000" />
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="f-unit">Unit</label>
              <select id="f-unit" value={form.original_unit} onChange={e => setForm({ ...form, original_unit: e.target.value })}>
                {UNITS.map(u => <option key={u} value={u}>{u}</option>)}
              </select>
              <small>Pint normalizes to kWh / kg / m³ on the API (D1).</small>
            </div>
            <div className="field">
              <label htmlFor="f-conf">Confidence 0–100</label>
              <input id="f-conf" type="number" min={0} max={100} value={form.confidence_score} onChange={e => setForm({ ...form, confidence_score: e.target.value })} />
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="f-src">Source</label>
              <select id="f-src" value={form.data_source_type} onChange={e => setForm({ ...form, data_source_type: e.target.value })}>
                {['MANUAL','CSV','EXCEL','API','SENSOR','OCR'].map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="f-meas">Measured / Estimated</label>
              <select id="f-meas" value={form.measured_or_estimated} onChange={e => setForm({ ...form, measured_or_estimated: e.target.value })}>
                <option value="MEASURED">MEASURED</option>
                <option value="ESTIMATED">ESTIMATED</option>
              </select>
            </div>
          </div>
          {issues.length > 0 && (
            <ul style={{ fontSize: '.83rem', color: 'var(--high)', paddingLeft: 18 }}>
              {issues.map((i, k) => <li key={k}>{i}</li>)}
            </ul>
          )}
          <button className="btn btn-primary" type="submit">Validate &amp; queue entry</button>
        </form>
        <div>
          <div className="panel panel-pad">
            <h2>Queued this session</h2>
            {saved.length === 0 ? (
              <div className="notice empty"><b>Nothing queued.</b> Validated entries appear here; the API persists them when live (C1 returns 201 ActivityData).</div>
            ) : (
              <ul style={{ paddingLeft: 18, fontSize: '.88rem' }}>{saved.map((s, i) => <li key={i} className="mono">{s}</li>)}</ul>
            )}
            <hr className="divider" />
            <h3>Import (C4)</h3>
            <p style={{ fontSize: '.84rem', color: 'var(--legend-ink)' }}>
              CSV/XLSX import validates headers with Pandera, checks MIME, hashes for duplicate imports,
              and returns <span className="mono">202 ImportJob + ValidationIssue[]</span>. Empty, corrupt, or
              password-protected files are rejected with safe errors.
            </p>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                ref={fileRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                aria-label="Import CSV or Excel file"
                onChange={e => handleFile(e.target.files?.[0])}
                style={{ border: '1px solid var(--line-strong)', borderRadius: 8, padding: 6, maxWidth: 260 }}
              />
              <button className="btn btn-ghost" type="button" onClick={() => fileRef.current?.click()}>Choose file</button>
            </div>
            {importSummary && <div className="notice" style={{ marginTop: 10 }}>{importSummary}</div>}
            {importRows.length > 0 && (
              <div className="table-wrap" style={{ marginTop: 10, maxHeight: 220, overflowY: 'auto' }}>
                <table className="data">
                  <thead>
                    <tr><th>Row</th><th>Subcategory</th><th className="n">Value</th><th>Unit</th><th>Issues</th></tr>
                  </thead>
                  <tbody>
                    {importRows.slice(0, 50).map(r => (
                      <tr key={r.row}>
                        <td className="mono">{r.row}</td>
                        <td>{r.data.activity_subcategory || '—'}</td>
                        <td className="n mono">{r.data.original_value || '—'}</td>
                        <td className="mono">{r.data.original_unit || '—'}</td>
                        <td>
                          {r.issues.length === 0
                            ? <span style={{ color: 'var(--low)' }}>OK</span>
                            : <span style={{ color: 'var(--high)' }}>{r.issues.map(i => `${i.severity}: ${i.code}`).join(' · ') || '—'}</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {importRows.some(r => r.issues.length) && (
              <ul style={{ fontSize: '.8rem', color: 'var(--high)', paddingLeft: 18 }}>
                {[...new Set(importRows.flatMap(r => r.issues.map(i => `${i.severity} ${i.code} — ${i.message}`)))].map((m, k) => <li key={k}>{m}</li>)}
              </ul>
            )}
          </div>
          <div className="panel panel-pad">
            <h2>Seed records</h2>
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>Subcategory</th><th>Category</th><th className="n">Value</th></tr></thead>
                <tbody>
                  {dataset.activity_data.slice(0, 8).map(a => (
                    <tr key={a.id}><td>{a.activity_subcategory}</td><td>{a.activity_category}</td>
                      <td className="n mono">{a.original_value} {a.original_unit}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
