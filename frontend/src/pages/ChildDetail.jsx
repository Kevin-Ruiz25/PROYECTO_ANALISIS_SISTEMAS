import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import CarnetPanel from '../components/CarnetPanel'
import ChildAlerts from '../components/ChildAlerts'
import GrowthChart from '../components/GrowthChart'
import VaccinationPanel from '../components/VaccinationPanel'
import { Empty, ErrorBanner, Field } from '../components/ui'
import { SEX, ageLabel, fmtDate, growthStatus, pctLabel, todayISO } from '../utils'

const MAX_MONTHS_OMS = 60

function Badge({ kind, p }) {
  const s = growthStatus(kind, p)
  if (!s) return <span className="muted">—</span>
  return (
    <span className="pct">
      {pctLabel(p)} <span className={`badge ${s.tone}`}>{s.text}</span>
    </span>
  )
}

export default function ChildDetail() {
  const { id } = useParams()
  const [child, setChild] = useState(null)
  const [communityName, setCommunityName] = useState('')
  const [records, setRecords] = useState([])
  const [reference, setReference] = useState(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('crecimiento')
  const [alertsKey, setAlertsKey] = useState(0)
  const bumpAlerts = () => setAlertsKey((k) => k + 1)

  const loadRecords = useCallback(
    () => api.get(`/children/${id}/growth`).then(setRecords).catch((e) => setError(e.message)),
    [id],
  )

  useEffect(() => {
    setError('')
    api.get(`/children/${id}`)
      .then(async (c) => {
        setChild(c)
        if (c.community_id) api.get(`/communities/${c.community_id}`).then((x) => setCommunityName(x.name)).catch(() => {})
        api.get(`/growth/reference?sex=${c.sex}`).then(setReference).catch((e) => setError(e.message))
        loadRecords()
      })
      .catch((e) => setError(e.message))
  }, [id, loadRecords])

  async function removeRecord(r) {
    if (!window.confirm(`¿Eliminar la medición del ${fmtDate(r.measured_on)}?`)) return
    setError('')
    try { await api.del(`/growth/${r.id}`); loadRecords(); bumpAlerts() } catch (e) { setError(e.message) }
  }

  if (!child) {
    return (
      <>
        <Link className="back" to="/ninos">Volver a niños</Link>
        {error ? <ErrorBanner message={error} /> : <p>Cargando…</p>}
      </>
    )
  }

  const ageNow = ageLabel(child.birth_date)
  // Niños menores de 2 años: eje hasta 24 meses (más legible). Si ya pasó de 2 años, hasta 60.
  const currentMonths = (Date.now() - new Date(child.birth_date)) / (30.4375 * 864e5)
  const latestMonths = Math.max(0, ...records.map((r) => r.age_months))
  const maxMonths = Math.max(currentMonths, latestMonths) > 24 ? MAX_MONTHS_OMS : 24
  const outOfRange = records.some((r) => r.weight_percentile === null)

  const points = (field) => records.filter((r) => r.age_months <= MAX_MONTHS_OMS)
    .map((r) => ({ age: r.age_months, value: r[field] }))

  return (
    <>
      <Link className="back" to="/ninos">Volver a niños</Link>
      <header className="detail-head">
        <h1>{child.full_name}</h1>
        <p>
          {ageNow} · {SEX[child.sex]}{communityName ? ` · ${communityName}` : ''}
        </p>
        <p className="muted">
          Padres o tutores: {child.parents.map((p) => p.full_name).join(', ') || 'sin asignar'}
        </p>
      </header>

      <ErrorBanner message={error} />
      <ChildAlerts childId={child.id} refreshKey={alertsKey} />

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'crecimiento'} className={tab === 'crecimiento' ? 'on' : ''}
          onClick={() => setTab('crecimiento')}>Crecimiento</button>
        <button role="tab" aria-selected={tab === 'vacunacion'} className={tab === 'vacunacion' ? 'on' : ''}
          onClick={() => setTab('vacunacion')}>Vacunación</button>
        <button role="tab" aria-selected={tab === 'carnet'} className={tab === 'carnet' ? 'on' : ''}
          onClick={() => setTab('carnet')}>Carnet digital</button>
      </div>

      {tab === 'carnet' && <CarnetPanel child={child} />}
      {tab === 'vacunacion' && <VaccinationPanel child={child} onChange={bumpAlerts} />}

      {tab === 'crecimiento' && (
        <>
      <section className="card">
        <h2>Registrar medición</h2>
        <MeasureForm child={child} onSaved={() => { loadRecords(); bumpAlerts() }} />
      </section>

      <section>
        <h2 className="section-title">Curvas de crecimiento</h2>
        {reference && (
          <div className="charts">
            <GrowthChart title="Peso para la edad" unit="kg" reference={reference.weight}
              points={points('weight_kg')} maxMonths={maxMonths} />
            <GrowthChart title="Talla para la edad" unit="cm" reference={reference.height}
              points={points('height_cm')} maxMonths={maxMonths} />
          </div>
        )}
        <p className="note">
          Referencia: patrones de crecimiento infantil de la OMS (0 a 5 años), según edad y sexo.
          Hasta los 24 meses la OMS usa la longitud (acostado) y después la talla (de pie).
        </p>
      </section>

      <section>
        <h2 className="section-title">Historial de mediciones</h2>
        {records.length === 0 ? (
          <Empty title="Aún no hay mediciones" text="Registra el peso y la talla para ver las curvas y los percentiles." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Fecha</th><th>Edad</th><th className="num">Peso (kg)</th><th>Peso para la edad</th>
                  <th className="num">Talla (cm)</th><th>Talla para la edad</th><th /></tr>
              </thead>
              <tbody>
                {[...records].reverse().map((r) => (
                  <tr key={r.id}>
                    <td>{fmtDate(r.measured_on)}</td>
                    <td>{formatAge(r.age_months)}</td>
                    <td className="num">{r.weight_kg}</td>
                    <td><Badge kind="weight" p={r.weight_percentile} /></td>
                    <td className="num">{r.height_cm}</td>
                    <td><Badge kind="height" p={r.height_percentile} /></td>
                    <td className="actions"><button className="link danger" onClick={() => removeRecord(r)}>Eliminar</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {outOfRange && <p className="note">Las mediciones después de los 5 años quedan guardadas, pero no tienen percentil con esta referencia.</p>}
        <p className="note">
          Los percentiles son una guía de apoyo. Un valor bajo el P5 o sobre el P95 debe ser evaluado por el personal de salud.
        </p>
      </section>
        </>
      )}
    </>
  )
}

function formatAge(months) {
  const m = Math.floor(months)
  if (m < 24) return `${m} ${m === 1 ? 'mes' : 'meses'}`
  const y = Math.floor(m / 12)
  const r = m % 12
  return r ? `${y} años ${r} m` : `${y} años`
}

function MeasureForm({ child, onSaved }) {
  const [f, setF] = useState({ measured_on: todayISO(), weight_kg: '', height_cm: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await api.post(`/children/${child.id}/growth`, {
        measured_on: f.measured_on, weight_kg: Number(f.weight_kg), height_cm: Number(f.height_cm),
      })
      setF({ measured_on: todayISO(), weight_kg: '', height_cm: '' })
      onSaved()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit}>
      <ErrorBanner message={error} />
      <div className="measure-grid">
        <Field label="Fecha de la medición">
          <input type="date" value={f.measured_on} onChange={set('measured_on')} min={child.birth_date} max={todayISO()} required />
        </Field>
        <Field label="Peso (kg)">
          <input type="number" inputMode="decimal" step="0.01" min="0.4" max="59" value={f.weight_kg} onChange={set('weight_kg')} required />
        </Field>
        <Field label="Talla (cm)" hint="Menores de 2 años: longitud acostado.">
          <input type="number" inputMode="decimal" step="0.1" min="21" max="149" value={f.height_cm} onChange={set('height_cm')} required />
        </Field>
        <button className="btn" disabled={busy}>{busy ? 'Guardando…' : 'Guardar medición'}</button>
      </div>
    </form>
  )
}
