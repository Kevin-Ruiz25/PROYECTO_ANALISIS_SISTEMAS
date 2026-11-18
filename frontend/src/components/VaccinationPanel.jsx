import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { ErrorBanner, Field, Modal } from './ui'
import { VAX_STATUS, fmtDate, monthsLabel, todayISO } from '../utils'

export default function VaccinationPanel({ child, onChange }) {
  const [card, setCard] = useState(null)
  const [error, setError] = useState('')
  const [applying, setApplying] = useState(null)
  const [onlyOpen, setOnlyOpen] = useState(false)

  const load = useCallback(
    () => api.get(`/children/${child.id}/vaccination-card`).then(setCard).catch((e) => setError(e.message)),
    [child.id],
  )
  useEffect(() => { load() }, [load])

  async function undo(item) {
    if (!window.confirm(`¿Quitar el registro de ${item.vaccine.name} (dosis ${item.vaccine.dose_number})?`)) return
    setError('')
    try { await api.del(`/vaccinations/${item.vaccination_id}`); load(); onChange?.() } catch (e) { setError(e.message) }
  }

  if (!card) return error ? <ErrorBanner message={error} /> : <p>Cargando…</p>

  const s = card.summary
  const rows = onlyOpen ? card.items.filter((i) => i.status === 'atrasada' || i.status === 'pendiente') : card.items

  return (
    <>
      <ErrorBanner message={error} />
      <div className="summary" role="status">
        <div><strong>{s.completa}</strong><span>de {s.total} dosis completas</span></div>
        <div className={s.atrasada ? 'bad' : ''}><strong>{s.atrasada}</strong><span>atrasadas</span></div>
        <div className={s.pendiente ? 'warn' : ''}><strong>{s.pendiente}</strong><span>pendientes ahora</span></div>
        <div><strong>{s.proxima}</strong><span>aún no tocan</span></div>
      </div>

      <label className="check">
        <input type="checkbox" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} />
        Mostrar solo atrasadas y pendientes
      </label>

      {rows.length === 0 ? (
        <p className="empty-line">No hay dosis atrasadas ni pendientes.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Vacuna</th><th>Dosis</th><th>Edad recomendada</th><th>Fecha recomendada</th>
                <th>Estado</th><th>Aplicada</th><th>Próxima dosis</th><th /></tr>
            </thead>
            <tbody>
              {rows.map((i) => {
                const st = VAX_STATUS[i.status]
                return (
                  <tr key={i.vaccine.id}>
                    <td>{i.vaccine.name}</td>
                    <td>{i.vaccine.dose_number}</td>
                    <td>{monthsLabel(i.vaccine.recommended_age_months)}</td>
                    <td>{fmtDate(i.due_date)}</td>
                    <td><span className={`badge ${st.tone}`}>{st.text}</span></td>
                    <td>{fmtDate(i.applied_on)}</td>
                    <td>{fmtDate(i.next_dose_on)}</td>
                    <td className="actions">
                      {i.vaccination_id
                        ? <button className="link danger" onClick={() => undo(i)}>Quitar registro</button>
                        : <button className="link" onClick={() => setApplying(i)}>Registrar aplicación</button>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="note">
        Una dosis se considera atrasada cuando pasan más de 30 días de su fecha recomendada.
        El esquema es el del catálogo de vacunas del centro de salud.
      </p>

      {applying && (
        <ApplyForm child={child} item={applying} onClose={() => setApplying(null)}
          onSaved={() => { setApplying(null); load(); onChange?.() }} />
      )}
    </>
  )
}

function ApplyForm({ child, item, onClose, onSaved }) {
  const [appliedOn, setAppliedOn] = useState(todayISO())
  const [nextDose, setNextDose] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await api.post(`/children/${child.id}/vaccinations`, {
        vaccine_id: item.vaccine.id, applied_on: appliedOn, next_dose_on: nextDose || null,
      })
      onSaved()
    } catch (err) { setError(err.message); setBusy(false) }
  }

  return (
    <Modal title="Registrar aplicación" onClose={onClose}>
      <form onSubmit={submit}>
        <p className="modal-sub">
          <strong>{item.vaccine.name}</strong>, dosis {item.vaccine.dose_number}, para {child.full_name}.
        </p>
        <ErrorBanner message={error} />
        <Field label="Fecha de aplicación">
          <input type="date" value={appliedOn} onChange={(e) => setAppliedOn(e.target.value)}
            min={child.birth_date} max={todayISO()} required autoFocus />
        </Field>
        <Field label="Fecha de la próxima dosis (opcional)" hint="Si la dejas vacía, se calcula según el esquema.">
          <input type="date" value={nextDose} onChange={(e) => setNextDose(e.target.value)} min={appliedOn} />
        </Field>
        <div className="modal-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Cancelar</button>
          <button className="btn" disabled={busy}>{busy ? 'Guardando…' : 'Guardar aplicación'}</button>
        </div>
      </form>
    </Modal>
  )
}
