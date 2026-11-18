import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Empty, ErrorBanner, Field, Modal, PageHeader } from '../components/ui'
import { monthsLabel } from '../utils'

const blank = { name: '', recommended_age_months: 0, dose_number: 1 }

export default function Vaccines() {
  const { user } = useAuth()
  const canEdit = user.role === 'admin' || user.role === 'manager'
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(null)

  const load = () => api.get('/vaccines').then(setItems).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  async function remove(v) {
    if (!window.confirm(`¿Eliminar ${v.name}, dosis ${v.dose_number}, del catálogo?`)) return
    setError('')
    try { await api.del(`/vaccines/${v.id}`); load() } catch (e) { setError(e.message) }
  }

  return (
    <>
      <PageHeader
        title="Catálogo de vacunas"
        subtitle="Esquema regular que usa el centro de salud para calcular dosis pendientes y atrasadas."
        action={canEdit && <button className="btn" onClick={() => setEditing(blank)}>Nueva vacuna</button>}
      />
      <p className="banner info" role="note">
        El catálogo inicial sigue el esquema del Ministerio de Salud (MSPAS) publicado en 2026. Puede cambiar según la
        disponibilidad de vacunas, por ejemplo hexavalente en lugar de pentavalente. Confirma con tu centro de salud
        y ajústalo aquí.{!canEdit && ' Solo el administrador o el encargado del centro pueden modificarlo.'}
      </p>
      <ErrorBanner message={error} />
      {items === null ? <p>Cargando…</p> : items.length === 0 ? (
        <Empty title="El catálogo está vacío" text="Agrega las vacunas del esquema para poder registrar aplicaciones." />
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Edad recomendada</th><th>Vacuna</th><th className="num">Dosis</th>{canEdit && <th />}</tr></thead>
            <tbody>
              {items.map((v) => (
                <tr key={v.id}>
                  <td>{monthsLabel(v.recommended_age_months)}</td>
                  <td>{v.name}</td>
                  <td className="num">{v.dose_number}</td>
                  {canEdit && (
                    <td className="actions">
                      <button className="link" onClick={() => setEditing(v)}>Editar</button>
                      <button className="link danger" onClick={() => remove(v)}>Eliminar</button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && <VaccineForm initial={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />}
    </>
  )
}

function VaccineForm({ initial, onClose, onSaved }) {
  const [f, setF] = useState({
    name: initial.name, recommended_age_months: initial.recommended_age_months, dose_number: initial.dose_number,
  })
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    setError('')
    const body = {
      name: f.name.trim(), recommended_age_months: Number(f.recommended_age_months), dose_number: Number(f.dose_number),
    }
    try {
      initial.id ? await api.put(`/vaccines/${initial.id}`, body) : await api.post('/vaccines', body)
      onSaved()
    } catch (err) { setError(err.message) }
  }

  return (
    <Modal title={initial.id ? 'Editar vacuna' : 'Nueva vacuna'} onClose={onClose}>
      <form onSubmit={submit}>
        <ErrorBanner message={error} />
        <Field label="Nombre" hint="Las dosis de una misma vacuna deben llevar exactamente el mismo nombre.">
          <input value={f.name} onChange={set('name')} required minLength={2} autoFocus />
        </Field>
        <div className="two">
          <Field label="Número de dosis"><input type="number" min="1" max="20" value={f.dose_number} onChange={set('dose_number')} required /></Field>
          <Field label="Edad recomendada (meses)" hint="0 = al nacer.">
            <input type="number" min="0" max="216" value={f.recommended_age_months} onChange={set('recommended_age_months')} required />
          </Field>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Cancelar</button>
          <button className="btn">Guardar cambios</button>
        </div>
      </form>
    </Modal>
  )
}
