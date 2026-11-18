import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, ErrorBanner, PageHeader } from '../components/ui'
import { fmtCell } from '../utils'

const TABS = [
  { kind: 'bajo-peso', label: 'Bajo peso', filter: true, help: 'Niños cuyo último control de peso está por debajo del percentil 5.' },
  { kind: 'sobrepeso', label: 'Sobrepeso', filter: true, help: 'Niños cuyo último control de peso está por encima del percentil 95.' },
  { kind: 'vacunas-incompletas', label: 'Vacunas incompletas', filter: true, help: 'Niños con al menos una dosis atrasada o pendiente, los más atrasados primero.' },
  { kind: 'cobertura', label: 'Cobertura por comunidad', filter: false, help: 'Cobertura = dosis aplicadas entre dosis que ya le tocaban a cada niño por su edad. Compara todas las comunidades.' },
  { kind: 'crecimiento', label: 'Crecimiento por comunidad', filter: false, help: 'Promedios del último control de cada niño. El percentil promedio es una guía descriptiva del grupo, no un diagnóstico.' },
  { kind: 'crecimiento-edad', label: 'Crecimiento por edad', filter: true, help: 'Mismos promedios agrupados por edad, para ver en qué etapa se concentran los problemas.' },
]

function Stat({ label, value, tone }) {
  return (
    <div className={`stat ${tone || ''}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  )
}

export default function Reports() {
  const [tab, setTab] = useState(TABS[0])
  const [communities, setCommunities] = useState([])
  const [communityId, setCommunityId] = useState('')
  const [summary, setSummary] = useState(null)
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  useEffect(() => { api.get('/communities').then(setCommunities).catch((e) => setError(e.message)) }, [])

  const q = communityId ? `?community_id=${communityId}` : ''
  useEffect(() => {
    api.get('/reports/summary' + q).then(setSummary).catch((e) => setError(e.message))
  }, [q])

  const load = useCallback(() => {
    setReport(null)
    setError('')
    api.get(`/reports/${tab.kind}` + q).then(setReport).catch((e) => setError(e.message))
  }, [tab, q])
  useEffect(() => { load() }, [load])

  async function exportAs(format) {
    setBusy(format); setError('')
    try { await api.download(`/reports/${tab.kind}/export?format=${format}` + (communityId ? `&community_id=${communityId}` : '')) }
    catch (e) { setError(e.message) } finally { setBusy('') }
  }

  const cov = summary?.vaccine_coverage_pct
  return (
    <>
      <PageHeader
        title="Reportes"
        subtitle="Situación de crecimiento y vacunación de los niños del centro de salud. Todo se puede descargar en Excel o PDF."
        action={
          <select value={communityId} onChange={(e) => setCommunityId(e.target.value)} aria-label="Filtrar por comunidad">
            <option value="">Todas las comunidades</option>
            {communities.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        }
      />
      <ErrorBanner message={error} />

      {summary && (
        <div className="stats">
          <Stat label="Niños registrados" value={summary.children} />
          <Stat label="Con bajo peso" value={summary.low_weight} tone={summary.low_weight ? 'danger' : ''} />
          <Stat label="Con sobrepeso" value={summary.high_weight} tone={summary.high_weight ? 'warn' : ''} />
          <Stat label="Vacunas incompletas" value={summary.incomplete_vaccines} tone={summary.incomplete_vaccines ? 'warn' : ''} />
          <Stat label="Sin ningún control" value={summary.without_measurements} />
          <Stat label="Cobertura de vacunas" value={cov === null || cov === undefined ? '—' : `${cov}%`} />
        </div>
      )}

      <div className="tabs wrap-tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.kind} role="tab" aria-selected={tab.kind === t.kind}
            className={tab.kind === t.kind ? 'on' : ''} onClick={() => setTab(t)}>{t.label}</button>
        ))}
      </div>

      <div className="toolbar">
        <p className="muted">
          {tab.help}
          {!tab.filter && communityId && ' (Este reporte compara todas las comunidades, por eso ignora el filtro.)'}
        </p>
        <div className="btn-row">
          <button className="btn ghost" onClick={() => exportAs('xlsx')} disabled={!report || !!busy}>
            {busy === 'xlsx' ? 'Preparando…' : 'Descargar Excel'}
          </button>
          <button className="btn" onClick={() => exportAs('pdf')} disabled={!report || !!busy}>
            {busy === 'pdf' ? 'Preparando…' : 'Descargar PDF'}
          </button>
        </div>
      </div>

      {report === null ? <p>Cargando…</p> : report.rows.length === 0 ? (
        <Empty title="Sin resultados" text="No hay niños que cumplan esta condición con los datos actuales. ¡Buena señal!" />
      ) : (
        <div className="table-wrap">
          <table>
            <caption className="sr-only">{report.title}</caption>
            <thead>
              <tr>{report.columns.map((c) => <th key={c.key} className={c.kind === 'int' || c.kind === 'float' ? 'num' : ''}>{c.label}</th>)}</tr>
            </thead>
            <tbody>
              {report.rows.map((r, i) => (
                <tr key={i} className={r[report.columns[0].key] === 'TOTAL' ? 'total-row' : ''}>
                  {report.columns.map((c) => (
                    <td key={c.key} className={(c.kind === 'int' || c.kind === 'float' ? 'num ' : '') + (c.key === 'detail' ? 'wrap' : '')}>
                      {fmtCell(r[c.key], c.kind)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
