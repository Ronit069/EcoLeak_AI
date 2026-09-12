// Modules C/D — Data & Activities: ledger execution + dry-run import + quality.
import { useMemo, useRef, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import {
  ApiError, createActivity, fetchActivities, fetchDataQuality, fetchProcesses, importActivities,
} from '../lib/api'
import { fmtNumber, fmtScore, fmtTimestamp, isNil, num } from '../lib/format'
import { useGroup } from '../lib/useApi'
import { useApp } from '../state/AppContext'
import type { DataQuality, ImportJob, ValidationIssue } from '../lib/types'
import {
  Banner, Empty, Gauge, Loading, SectionHead, SourceStamp, ValidationBadge,
} from '../components/ui'

const CATEGORIES = ['ELECTRICITY', 'FUEL', 'MATERIAL', 'WATER', 'TRANSPORT', 'WASTE', 'REFRIGERANT', 'STEAM', 'OTHER'] as const
const SOURCES = ['MANUAL', 'CSV', 'EXCEL', 'API', 'SENSOR', 'OCR'] as const

const entrySchema = z.object({
  activity_category: z.enum(CATEGORIES),
  activity_subcategory: z.string().min(1, 'Required').max(100),
  original_value: z.string().refine((v) => Number.isFinite(Number(v)) && Number(v) >= 0, 'Must be a number ≥ 0'),
  original_unit: z.string().min(1, 'Required').max(30),
  source_name: z.string().max(150).optional(),
  data_source_type: z.enum(SOURCES),
  measured_or_estimated: z.enum(['MEASURED', 'ESTIMATED']),
  confidence_score: z.string().optional().refine((v) => !v || (Number(v) >= 0 && Number(v) <= 100), '0–100'),
})
type EntryForm = z.infer<typeof entrySchema>

export function DataActivities() {
  const { ids, refreshKey, refresh } = useApp()
  const activities = useGroup(() => fetchActivities(ids.facility_id, ids.reporting_period_id), [ids.facility_id, ids.reporting_period_id, refreshKey])
  const processes = useGroup(() => fetchProcesses(ids.facility_id), [ids.facility_id, refreshKey])
  const [quality, setQuality] = useState<DataQuality | null>(null)
  const [qualityError, setQualityError] = useState<string | null>(null)
  const [job, setJob] = useState<ImportJob | null>(null)
  const [importError, setImportError] = useState<string | null>(null)

  const rows = activities.data ?? []
  const dq = num(quality?.total_score)
  const processName = (pid: string | null) => (pid ? processes.data?.find((p) => p.id === pid)?.name ?? '—' : '—')
  const issueCounts = (sev: string) => (quality?.issues ?? []).filter((i) => i.severity === sev).length

  return (
    <>
      <div className="panel-head">
        <div>
          <span className="panel-title">Data Ingestion &amp; Activity Ledger</span>
          <span className="panel-sub" style={{ marginLeft: 10 }}>PANDERA &amp; PYDANTIC VALIDATION · UNIT NORMALIZATION</span>
        </div>
        <div className="spacer" />
        <SourceStamp source={activities.source} />
      </div>

      <div className="panel-body">
        {/* Data Quality & Provenance */}
        <div className="section">
          <div className="section-head">
            <h2>Data Quality &amp; Confidence Assessment</h2>
            <button className="primary" onClick={() => loadQuality()}>ASSESS REPORTING PERIOD</button>
          </div>
          <div className="section-body">
            {qualityError ? <Banner kind="error" title={qualityError}>{'\u00a0'}</Banner> : null}
            {dq !== null && dq < 60 ? (
              <Banner kind="warning" title="PROVISIONAL QUALITY">
                Data quality is below 60. Emission calculations and recommendations carry wider confidence intervals.
              </Banner>
            ) : null}
            {quality ? (
              <>
                <div className="grid-2">
                  <div>
                    <Gauge label="Overall Score" value={quality.total_score} />
                    <Gauge label="Completeness" value={quality.completeness_score} />
                    <Gauge label="Source Quality" value={quality.source_quality_score} />
                  </div>
                  <div>
                    <Gauge label="Factor Provenance" value={quality.factor_quality_score} />
                    <Gauge label="Temporal Match" value={quality.temporal_quality_score} />
                    <Gauge label="Unit Standard" value={quality.unit_quality_score} />
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 14, marginTop: 14, flexWrap: 'wrap' }}>
                  <span className="topstat"><ValidationBadge severity="ERROR" /> {issueCounts('ERROR')} errors</span>
                  <span className="topstat"><ValidationBadge severity="WARNING" /> {issueCounts('WARNING')} warnings</span>
                  <span className="topstat"><ValidationBadge severity="INFO" /> {issueCounts('INFO')} info</span>
                  <span className="topstat"><ValidationBadge severity="CONFIRMATION_REQUIRED" /> {issueCounts('CONFIRMATION_REQUIRED')} confirmation</span>
                </div>
              </>
            ) : (
              <div className="empty-block">NO ASSESSMENT RUN FOR THIS PERIOD — CLICK &quot;ASSESS REPORTING PERIOD&quot;</div>
            )}
            {quality?.issues?.length ? (
              <IssueList issues={quality.issues} />
            ) : null}
          </div>
        </div>

        {/* Activity Ledger Table */}
        <div className="section">
          <div className="section-head">
            <h2>Factory Activity Ledger</h2>
            <span className="mono tiny faint">{rows.length} ACTIVITY RECORDS LOGGED</span>
          </div>
          {activities.loading ? <Loading what="ledger" /> : null}
          {!activities.loading && rows.length === 0 ? <div className="section-body"><Empty>NO ACTIVITY DATA FOR THIS PERIOD</Empty></div> : null}
          {rows.length ? (
            <table className="grid">
              <thead>
                <tr>
                  <th>Process</th>
                  <th>Category / Stream</th>
                  <th className="num">Original Uploaded</th>
                  <th className="num">Normalized Standard</th>
                  <th>Data Source</th>
                  <th className="num">Quality</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id}>
                    <td style={{ fontWeight: 600 }}>{processName(a.process_id)}</td>
                    <td className="mono tiny">
                      {a.activity_category}
                      <div className="faint" style={{ fontWeight: 400 }}>{a.activity_subcategory}</div>
                    </td>
                    <td className="num nowrap">
                      {fmtNumber(a.original_value, 2)} <span className="faint">{a.original_unit}</span>
                    </td>
                    <td className="num nowrap" style={{ color: 'var(--cyan)' }}>
                      {fmtNumber(a.normalized_value, 2)} <span className="faint">{a.normalized_unit}</span>
                    </td>
                    <td className="mono tiny">
                      {a.data_source_type}
                      <div className="faint">{a.source_name ?? '—'}</div>
                    </td>
                    <td className="num">{isNil(a.confidence_score) ? '—' : fmtScore(a.confidence_score)}</td>
                    <td>
                      <span className={`badge ${a.measured_or_estimated === 'MEASURED' ? 'stamp-REAL' : 'stamp-UNAVAILABLE'}`}>
                        {a.measured_or_estimated === 'MEASURED' ? 'MEASURED' : 'ESTIMATED'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </div>

        {/* Batch File Ingestion */}
        <div className="section">
          <div className="section-head">
            <h2>Batch Ingestion (CSV / Excel)</h2>
            <span className="mono tiny faint">PANDERA PRE-VALIDATION WITH DRY-RUN</span>
          </div>
          <div className="section-body">
            <ImportPanel
              onDone={(j) => { setJob(j); setImportError(null); refresh() }}
              onError={(m) => setImportError(m)}
            />
            {importError ? <Banner kind="error" title={importError}>{'\u00a0'}</Banner> : null}
            {job ? <ImportReport job={job} /> : null}
          </div>
        </div>

        {/* Manual Activity Data Entry */}
        <div className="section">
          <div className="section-head">
            <h2>Manual Activity Data Entry</h2>
            <span className="mono tiny faint">CLIENT-SIDE ZOD VALIDATION</span>
          </div>
          <div className="section-body">
            <ManualEntry
              onSubmit={async (body) => {
                try {
                  await createActivity(ids.facility_id, {
                    ...(body as unknown as import('../lib/api').ActivityCreateBody),
                    reporting_period_id: ids.reporting_period_id,
                  })
                  refresh()
                  return null
                } catch (err) {
                  if (err instanceof ApiError && err.errorCode === 'CONFIRMATION_REQUIRED') {
                    return 'Ambiguous unit conversion requires a density/assumption — this is a decision, not an error. Refused to convert silently.'
                  }
                  return err instanceof Error ? err.message : 'Failed'
                }
              }}
            />
          </div>
        </div>
      </div>
    </>
  )

  async function loadQuality() {
    try {
      setQualityError(null)
      setQuality(await fetchDataQuality(ids.facility_id, ids.reporting_period_id))
    } catch (e) {
      setQualityError(e instanceof Error ? e.message : 'Failed to assess quality')
    }
  }
}

function IssueList({ issues }: { issues: ValidationIssue[] }) {
  if (!issues.length) return null
  return (
    <table className="grid" style={{ marginTop: 14 }}>
      <thead>
        <tr>
          <th>Severity</th>
          <th>Issue Code</th>
          <th>Diagnostic Message</th>
          <th>Field Reference</th>
        </tr>
      </thead>
      <tbody>
        {issues.map((i, idx) => (
          <tr key={`${i.code}-${idx}`}>
            <td><ValidationBadge severity={i.severity} /></td>
            <td className="mono tiny">{i.code}</td>
            <td>{i.message}</td>
            <td className="mono tiny faint">{i.field ?? '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ImportPanel({ onDone, onError }: { onDone: (j: ImportJob) => void; onError: (m: string) => void }) {
  const { ids } = useApp()
  const fileRef = useRef<HTMLInputElement>(null)
  const [sheet, setSheet] = useState('')
  const [dryRun, setDryRun] = useState(true)
  const [busy, setBusy] = useState(false)

  async function run() {
    const file = fileRef.current?.files?.[0]
    if (!file) { onError('Choose a .csv or .xlsx file first.'); return }
    setBusy(true)
    try {
      const job = await importActivities({ file, facilityId: ids.facility_id, periodId: ids.reporting_period_id, sheet: sheet || undefined, dryRun })
      onDone(job)
    } catch (e) {
      if (e instanceof ApiError && e.errorCode === 'DUPLICATE_IMPORT') {
        onError('DUPLICATE IMPORT — this file was already imported for this facility/period.')
      } else {
        onError(e instanceof Error ? e.message : 'Import failed')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="btn-row" style={{ flexWrap: 'wrap' }}>
        <input ref={fileRef} type="file" accept=".csv,.xlsx" aria-label="Activity file" style={{ maxWidth: 280 }} />
        <input value={sheet} onChange={(e) => setSheet(e.target.value)} placeholder="sheet (optional)" aria-label="Excel sheet" style={{ width: 140 }} />
        <label className="mono tiny muted" style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} style={{ width: 'auto' }} /> Dry-Run Simulation
        </label>
        <button className="primary" onClick={run} disabled={busy}>{busy ? 'VALIDATING…' : 'PARSE & INGEST'}</button>
      </div>
      <p className="mono tiny faint" style={{ marginTop: 8 }}>
        Supported: CSV, XLSX · Maximum 20,000 rows · Dry-run validates without database commitment.
      </p>
    </div>
  )
}

function ImportReport({ job }: { job: ImportJob }) {
  const bySeverity = useMemo(() => {
    const map: Record<string, number> = {}
    for (const i of job.row_issues) map[i.severity] = (map[i.severity] ?? 0) + 1
    return map
  }, [job])

  return (
    <div style={{ marginTop: 14, padding: 12, background: 'var(--surface-2)', borderRadius: 'var(--r-xs)', border: '1px solid var(--border)' }}>
      <div className="btn-row" style={{ marginBottom: 8 }}>
        <span className="badge">INGESTION JOB {job.status}</span>
        <span className="tiny faint mono">ID: {job.import_id.slice(0, 12)}…</span>
      </div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
        {Object.entries(bySeverity).map(([sev, n]) => (
          <span key={sev} className="topstat">
            <ValidationBadge severity={sev as ValidationIssue['severity']} /> <span className="mono tiny">{n}</span>
          </span>
        ))}
      </div>
      {job.row_issues.length ? (
        <table className="grid">
          <thead>
            <tr>
              <th className="num">Row</th>
              <th>Severity</th>
              <th>Code</th>
              <th>Diagnostic Message</th>
              <th>Raw Row Content</th>
            </tr>
          </thead>
          <tbody>
            {job.row_issues.map((i, idx) => {
              const rowNo = (i.details?.row_number as number | undefined) ?? '—'
              const raw = i.details?.raw_row
              return (
                <tr key={idx}>
                  <td className="num">{String(rowNo)}</td>
                  <td><ValidationBadge severity={i.severity} /></td>
                  <td className="mono tiny">{i.code}</td>
                  <td>{i.message}</td>
                  <td className="mono tiny faint" style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {raw ? JSON.stringify(raw) : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      ) : (
        <p className="mono tiny" style={{ color: 'var(--emerald)' }}>✓ All records passed schema and range validation clean.</p>
      )}
    </div>
  )
}

function ManualEntry({ onSubmit }: { onSubmit: (data: EntryForm) => Promise<string | null> }) {
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<EntryForm>({
    resolver: zodResolver(entrySchema),
    defaultValues: {
      activity_category: 'FUEL',
      activity_subcategory: 'Natural Gas Combustion',
      original_value: '95000',
      original_unit: 'm3',
      data_source_type: 'MANUAL',
      measured_or_estimated: 'MEASURED',
      confidence_score: '90',
    },
  })
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState(false)

  const onValid = async (d: EntryForm) => {
    setError(null); setOk(false)
    const err = await onSubmit(d)
    if (err) setError(err)
    else { setOk(true); reset() }
  }

  return (
    <form onSubmit={handleSubmit(onValid)}>
      {error ? <Banner kind="error" title="VALIDATION">{error}</Banner> : null}
      {ok ? <Banner kind="info" title="RECORD INSERTED">Activity successfully added to current facility ledger.</Banner> : null}

      <div className="form-grid">
        <div className="field">
          <label htmlFor="f-cat">Activity Category</label>
          <select id="f-cat" {...register('activity_category')}>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-sub">Subcategory / Fuel / Stream</label>
          <input id="f-sub" {...register('activity_subcategory')} />
          {errors.activity_subcategory ? <span className="tiny" style={{ color: 'var(--coral)' }}>{errors.activity_subcategory.message}</span> : null}
        </div>
        <div className="field">
          <label htmlFor="f-val">Measured Quantity</label>
          <input id="f-val" {...register('original_value')} inputMode="decimal" />
          {errors.original_value ? <span className="tiny" style={{ color: 'var(--coral)' }}>{errors.original_value.message}</span> : null}
        </div>
        <div className="field">
          <label htmlFor="f-unit">Input Unit (e.g. kWh, m3, L, kg)</label>
          <input id="f-unit" {...register('original_unit')} />
          {errors.original_unit ? <span className="tiny" style={{ color: 'var(--coral)' }}>{errors.original_unit.message}</span> : null}
        </div>
        <div className="field">
          <label htmlFor="f-src">Ingestion Origin</label>
          <select id="f-src" {...register('data_source_type')}>
            {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-mod">Measurement Quality</label>
          <select id="f-mod" {...register('measured_or_estimated')}>
            <option value="MEASURED">MEASURED (Utility Meter / Invoices)</option>
            <option value="ESTIMATED">ESTIMATED (Operating Hours Run-time)</option>
          </select>
        </div>
      </div>

      <button className="primary" type="submit" disabled={isSubmitting} style={{ marginTop: 8 }}>
        {isSubmitting ? 'COMMITTING TO LEDGER…' : 'APPEND ACTIVITY TO LEDGER'}
      </button>
    </form>
  )
}
