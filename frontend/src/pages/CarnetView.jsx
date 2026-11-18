import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { ErrorBanner, Field, PageHeader } from '../components/ui'
import { SEX, VAX_STATUS, ageLabel, fmtDate, growthStatus, pctLabel } from '../utils'

function formatAge(months) {
  const m = Math.floor(months)
  if (m < 24) return `${m} ${m === 1 ? 'mes' : 'meses'}`
  const y = Math.floor(m / 12)
  return m % 12 ? `${y} años ${m % 12} m` : `${y} años`
}

function Pct({ kind, p }) {
  const s = growthStatus(kind, p)
  if (!s) return <span className="muted">—</span>
  return <span className="pct">{pctLabel(p)} <span className={`badge ${s.tone}`}>{s.text}</span></span>
}

export default function CarnetView() {
  const { token } = useParams()
  const { user } = useAuth()
  const [pin, setPin] = useState('')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // El carnet solo lo abre un padre o tutor autorizado (el personal usa la ficha del niño).
  if (user.role !== 'parent') {
    return (
      <>
        <PageHeader title="Carnet digital" />
        <p className="banner info" role="note">
          El carnet digital solo puede abrirlo el padre, la madre o el tutor autorizado con su cuenta y su PIN.
          El personal de salud consulta esta información desde la ficha de cada niño.
        </p>
        <Link className="back" to="/ninos">Ir a niños</Link>
      </>
    )
  }

  async function open(e) {
    e.preventDefault()
    setError(''); setBusy(true)
    try {
      setData(await api.post(`/carnet/${encodeURIComponent(token)}/open`, { pin: pin.trim() }))
      setPin('')
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  if (!data) {
    return (
      <>
        <PageHeader title="Carnet digital" subtitle="Escribe el PIN de 6 dígitos que te entregó el centro de salud." />
        <form className="card narrow" onSubmit={open}>
          <ErrorBanner message={error} />
          <Field label="PIN del carnet" hint="Si lo olvidaste o se bloqueó, pide uno nuevo en el centro de salud.">
            <input className="pin-input" value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
              inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}" maxLength={6} required autoFocus />
          </Field>
          <button className="btn" disabled={busy || pin.length < 6}>{busy ? 'Verificando…' : 'Abrir carnet'}</button>
        </form>
        <Link className="back" to="/mis-ninos">Volver a mis hijos</Link>
      </>
    )
  }

  const s = data.vaccination.summary
  const vaccines = data.vaccination.items
  return (
    <>
      <div className="no-print toolbar">
        <Link className="back" to="/mis-ninos">Volver a mis hijos</Link>
        <div className="row">
          <button className="btn ghost" onClick={() => window.print()}>Imprimir</button>
          <button className="btn ghost" onClick={() => setData(null)}>Cerrar carnet</button>
        </div>
      </div>

      <div className="print-area carnet">
        <header className="detail-head">
          <p className="muted">Carnet digital · SCCVI</p>
          <h1>{data.child_name}</h1>
          <p>{ageLabel(data.birth_date)} · {SEX[data.sex]} · nació el {fmtDate(data.birth_date)}
            {data.community_name ? ` · ${data.community_name}` : ''}</p>
        </header>

        <section>
          <h2 className="section-title">Vacunas</h2>
          <p className="muted">{s.completa} de {s.total} dosis aplicadas
            {s.atrasada > 0 && <> · <strong className="bad-text">{s.atrasada} atrasadas</strong></>}
            {s.pendiente > 0 && <> · {s.pendiente} pendientes ahora</>}</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Vacuna</th><th>Dosis</th><th>Estado</th><th>Aplicada</th><th>Próxima dosis</th></tr></thead>
              <tbody>
                {vaccines.map((i) => {
                  const st = VAX_STATUS[i.status]
                  return (
                    <tr key={i.vaccine.id}>
                      <td>{i.vaccine.name}</td>
                      <td>{i.vaccine.dose_number}</td>
                      <td><span className={`badge ${st.tone}`}>{st.text}</span></td>
                      <td>{fmtDate(i.applied_on)}</td>
                      <td>{i.applied_on ? fmtDate(i.next_dose_on) : `Corresponde: ${fmtDate(i.due_date)}`}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <h2 className="section-title">Últimos controles de peso y talla</h2>
          {data.growth.length === 0 ? (
            <p className="muted">Todavía no hay controles registrados.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Fecha</th><th>Edad</th><th className="num">Peso (kg)</th><th>Peso para la edad</th>
                  <th className="num">Talla (cm)</th><th>Talla para la edad</th></tr></thead>
                <tbody>
                  {data.growth.map((r) => (
                    <tr key={r.id}>
                      <td>{fmtDate(r.measured_on)}</td>
                      <td>{formatAge(r.age_months)}</td>
                      <td className="num">{r.weight_kg}</td>
                      <td><Pct kind="weight" p={r.weight_percentile} /></td>
                      <td className="num">{r.height_cm}</td>
                      <td><Pct kind="height" p={r.height_percentile} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="note">Los percentiles comparan con los patrones de la OMS y son solo una guía. Ante cualquier duda, consulta al personal de salud.</p>
        </section>
      </div>
    </>
  )
}
