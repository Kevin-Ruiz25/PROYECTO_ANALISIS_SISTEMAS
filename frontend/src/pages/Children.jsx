import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Empty, ErrorBanner, Field, Modal, PageHeader } from '../components/ui'
import { SEX, ageLabel, todayISO } from '../utils'

const blank = { full_name: '', birth_date: '', sex: 'M', community_id: null, parents: [] }

export default function Children() {
  const [items, setItems] = useState(null)
  const [communities, setCommunities] = useState([])
  const [q, setQ] = useState('')
  const [communityId, setCommunityId] = useState('')
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(null)

  useEffect(() => { api.get('/communities').then(setCommunities).catch((e) => setError(e.message)) }, [])

  const load = () => {
    const p = new URLSearchParams()
    if (q.trim()) p.set('q', q.trim())
    if (communityId) p.set('community_id', communityId)
    return api.get('/children?' + p).then(setItems).catch((e) => setError(e.message))
  }
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t) }, [q, communityId])

  const commName = (id) => communities.find((c) => c.id === id)?.name || '—'

  async function remove(c) {
    if (!window.confirm(`¿Eliminar a ${c.full_name} y todo su historial?`)) return
    setError('')
    try { await api.del(`/children/${c.id}`); load() } catch (e) { setError(e.message) }
  }

  return (
    <>
      <PageHeader
        title="Niños"
        subtitle="Registro de los niños atendidos en el centro de salud."
        action={<button className="btn" onClick={() => setEditing(blank)}>Registrar niño</button>}
      />
      <div className="filters">
        <input type="search" placeholder="Buscar por nombre" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar" />
        <select value={communityId} onChange={(e) => setCommunityId(e.target.value)} aria-label="Comunidad">
          <option value="">Todas las comunidades</option>
          {communities.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>
      <ErrorBanner message={error} />
      {items === null ? <p>Cargando…</p> : items.length === 0 ? (
        <Empty title="No se encontraron niños" text="Cambia la búsqueda o registra al primer niño."
          action={<button className="btn" onClick={() => setEditing(blank)}>Registrar niño</button>} />
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Nombre</th><th>Edad</th><th>Sexo</th><th>Comunidad</th><th>Padres o tutores</th><th /></tr></thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id}>
                  <td><Link className="name-link" to={`/ninos/${c.id}`}>{c.full_name}</Link></td>
                  <td>{ageLabel(c.birth_date)}</td>
                  <td>{SEX[c.sex]}</td>
                  <td>{commName(c.community_id)}</td>
                  <td>{c.parents.map((p) => p.full_name).join(', ') || '—'}</td>
                  <td className="actions">
                    <Link className="link" to={`/ninos/${c.id}`}>Ver crecimiento</Link>
                    <button className="link" onClick={() => setEditing(c)}>Editar</button>
                    <button className="link danger" onClick={() => remove(c)}>Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && <ChildForm initial={editing} communities={communities} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />}
    </>
  )
}

function ChildForm({ initial, communities, onClose, onSaved }) {
  const [f, setF] = useState({
    full_name: initial.full_name, birth_date: initial.birth_date, sex: initial.sex,
    community_id: initial.community_id ?? '', parent_ids: initial.parents.map((p) => p.id),
  })
  const [allParents, setAllParents] = useState([])
  const [filter, setFilter] = useState('')
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  useEffect(() => { api.get('/parents').then(setAllParents).catch((e) => setError(e.message)) }, [])

  const toggle = (id) =>
    setF((s) => ({ ...s, parent_ids: s.parent_ids.includes(id) ? s.parent_ids.filter((x) => x !== id) : [...s.parent_ids, id] }))

  const visible = allParents.filter((p) => {
    const t = filter.trim().toLowerCase()
    return f.parent_ids.includes(p.id) || !t || p.full_name.toLowerCase().includes(t) || p.dpi.includes(t)
  })

  async function submit(e) {
    e.preventDefault()
    setError('')
    const body = {
      full_name: f.full_name.trim(), birth_date: f.birth_date, sex: f.sex,
      community_id: f.community_id ? Number(f.community_id) : null, parent_ids: f.parent_ids,
    }
    try {
      initial.id ? await api.patch(`/children/${initial.id}`, body) : await api.post('/children', body)
      onSaved()
    } catch (err) { setError(err.message) }
  }

  return (
    <Modal title={initial.id ? 'Editar niño' : 'Registrar niño'} onClose={onClose}>
      <form onSubmit={submit}>
        <ErrorBanner message={error} />
        <Field label="Nombre completo"><input value={f.full_name} onChange={set('full_name')} required minLength={2} autoFocus /></Field>
        <div className="two">
          <Field label="Fecha de nacimiento"><input type="date" value={f.birth_date} onChange={set('birth_date')} max={todayISO()} required /></Field>
          <Field label="Sexo">
            <select value={f.sex} onChange={set('sex')}>
              {Object.entries(SEX).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Comunidad">
          <select value={f.community_id} onChange={set('community_id')}>
            <option value="">Sin comunidad</option>
            {communities.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        <fieldset className="picker">
          <legend>Padres o tutores</legend>
          <input type="search" placeholder="Buscar por nombre o DPI" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Buscar padre o tutor" />
          <div className="picker-list">
            {visible.length === 0 && <small>No hay resultados. Registra al padre o tutor en la sección Padres de familia.</small>}
            {visible.map((p) => (
              <label key={p.id}>
                <input type="checkbox" checked={f.parent_ids.includes(p.id)} onChange={() => toggle(p.id)} />
                {p.full_name} <small>{p.dpi}</small>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="modal-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Cancelar</button>
          <button className="btn">Guardar cambios</button>
        </div>
      </form>
    </Modal>
  )
}
