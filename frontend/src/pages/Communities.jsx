import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, ErrorBanner, Field, Modal, PageHeader } from '../components/ui'

const blank = { name: '', location: '', estimated_families: 0 }

export default function Communities() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(null) // null | {id?, ...campos}

  const load = () => api.get('/communities').then(setItems).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  async function remove(c) {
    if (!window.confirm(`¿Eliminar la comunidad ${c.name}?`)) return
    setError('')
    try { await api.del(`/communities/${c.id}`); load() } catch (e) { setError(e.message) }
  }

  return (
    <>
      <PageHeader
        title="Comunidades"
        subtitle="Aldeas, barrios y localidades que atiende el centro de salud."
        action={<button className="btn" onClick={() => setEditing(blank)}>Nueva comunidad</button>}
      />
      <ErrorBanner message={error} />
      {items === null ? <p>Cargando…</p> : items.length === 0 ? (
        <Empty title="Aún no hay comunidades" text="Registra la primera para poder asociar familias y niños."
          action={<button className="btn" onClick={() => setEditing(blank)}>Nueva comunidad</button>} />
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Nombre</th><th>Ubicación</th><th className="num">Familias (est.)</th><th /></tr></thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>{c.location || '—'}</td>
                  <td className="num">{c.estimated_families}</td>
                  <td className="actions">
                    <button className="link" onClick={() => setEditing(c)}>Editar</button>
                    <button className="link danger" onClick={() => remove(c)}>Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && <CommunityForm initial={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />}
    </>
  )
}

function CommunityForm({ initial, onClose, onSaved }) {
  const [f, setF] = useState({ name: initial.name, location: initial.location || '', estimated_families: initial.estimated_families })
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    setError('')
    const body = { name: f.name.trim(), location: f.location.trim() || null, estimated_families: Number(f.estimated_families) || 0 }
    try {
      initial.id ? await api.put(`/communities/${initial.id}`, body) : await api.post('/communities', body)
      onSaved()
    } catch (err) { setError(err.message) }
  }

  return (
    <Modal title={initial.id ? 'Editar comunidad' : 'Nueva comunidad'} onClose={onClose}>
      <form onSubmit={submit}>
        <ErrorBanner message={error} />
        <Field label="Nombre"><input value={f.name} onChange={set('name')} required minLength={2} autoFocus /></Field>
        <Field label="Ubicación" hint="Municipio, referencia o dirección."><input value={f.location} onChange={set('location')} /></Field>
        <Field label="Número estimado de familias"><input type="number" min="0" value={f.estimated_families} onChange={set('estimated_families')} /></Field>
        <div className="modal-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Cancelar</button>
          <button className="btn">Guardar cambios</button>
        </div>
      </form>
    </Modal>
  )
}
