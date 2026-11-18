import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, ErrorBanner, Field, Modal, PageHeader } from '../components/ui'
import { CHANNEL } from '../utils'

const blank = { full_name: '', dpi: '', phone: '', email: '', preferred_channel: 'email', community_id: '' }

export default function Parents() {
  const [items, setItems] = useState(null)
  const [communities, setCommunities] = useState([])
  const [q, setQ] = useState('')
  const [communityId, setCommunityId] = useState('')
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(null)
  const [access, setAccess] = useState(null) // credenciales recién creadas

  useEffect(() => { api.get('/communities').then(setCommunities).catch((e) => setError(e.message)) }, [])

  const load = () => {
    const p = new URLSearchParams()
    if (q.trim()) p.set('q', q.trim())
    if (communityId) p.set('community_id', communityId)
    return api.get('/parents?' + p).then(setItems).catch((e) => setError(e.message))
  }
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t) }, [q, communityId])

  const commName = (id) => communities.find((c) => c.id === id)?.name || '—'

  async function remove(p) {
    if (!window.confirm(`¿Eliminar a ${p.full_name}?`)) return
    setError('')
    try { await api.del(`/parents/${p.id}`); load() } catch (e) { setError(e.message) }
  }

  async function grant(p) {
    const msg = p.user_id
      ? `Se restablecerá la contraseña de ${p.full_name} y la anterior dejará de funcionar. ¿Continuar?`
      : `Se creará una cuenta para ${p.full_name} con su correo ${p.email || ''}. ¿Continuar?`
    if (!window.confirm(msg)) return
    setError('')
    try { setAccess({ name: p.full_name, ...(await api.post(`/parents/${p.id}/access`, {})) }); load() } catch (e) { setError(e.message) }
  }

  return (
    <>
      <PageHeader
        title="Padres de familia"
        subtitle="Padres y tutores, con el canal por el que desean recibir avisos."
        action={<button className="btn" onClick={() => setEditing(blank)}>Nuevo padre o tutor</button>}
      />
      <div className="filters">
        <input type="search" placeholder="Buscar por nombre o DPI" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar" />
        <select value={communityId} onChange={(e) => setCommunityId(e.target.value)} aria-label="Comunidad">
          <option value="">Todas las comunidades</option>
          {communities.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>
      <ErrorBanner message={error} />
      {items === null ? <p>Cargando…</p> : items.length === 0 ? (
        <Empty title="No se encontraron padres o tutores" text="Cambia la búsqueda o registra uno nuevo." />
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Nombre</th><th>DPI</th><th>Teléfono</th><th>Aviso por</th><th>Comunidad</th><th>Cuenta</th><th /></tr></thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id}>
                  <td>{p.full_name}</td>
                  <td>{p.dpi}</td>
                  <td>{p.phone || '—'}</td>
                  <td>{CHANNEL[p.preferred_channel]}</td>
                  <td>{commName(p.community_id)}</td>
                  <td>{p.user_id ? <span className="badge ok">Con acceso</span> : <span className="muted">Sin cuenta</span>}</td>
                  <td className="actions">
                    <button className="link" onClick={() => grant(p)} disabled={!p.email}
                      title={p.email ? '' : 'Registra primero su correo electrónico'}>
                      {p.user_id ? 'Restablecer acceso' : 'Crear acceso'}
                    </button>
                    <button className="link" onClick={() => setEditing(p)}>Editar</button>
                    <button className="link danger" onClick={() => remove(p)}>Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {access && <AccessModal data={access} onClose={() => setAccess(null)} />}
      {editing && <ParentForm initial={editing} communities={communities} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />}
    </>
  )
}

function ParentForm({ initial, communities, onClose, onSaved }) {
  const [f, setF] = useState({
    full_name: initial.full_name, dpi: initial.dpi, phone: initial.phone || '', email: initial.email || '',
    preferred_channel: initial.preferred_channel, community_id: initial.community_id ?? '',
  })
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    setError('')
    const body = {
      full_name: f.full_name.trim(), phone: f.phone.trim() || null, email: f.email.trim() || null,
      preferred_channel: f.preferred_channel, community_id: f.community_id ? Number(f.community_id) : null,
    }
    try {
      initial.id ? await api.patch(`/parents/${initial.id}`, body) : await api.post('/parents', { ...body, dpi: f.dpi.trim() })
      onSaved()
    } catch (err) { setError(err.message) }
  }

  return (
    <Modal title={initial.id ? 'Editar padre o tutor' : 'Nuevo padre o tutor'} onClose={onClose}>
      <form onSubmit={submit}>
        <ErrorBanner message={error} />
        <Field label="Nombre completo"><input value={f.full_name} onChange={set('full_name')} required minLength={2} autoFocus /></Field>
        <Field label="DPI" hint={initial.id ? 'El DPI no se puede cambiar.' : undefined}>
          <input value={f.dpi} onChange={set('dpi')} required minLength={5} disabled={!!initial.id} inputMode="numeric" />
        </Field>
        <div className="two">
          <Field label="Teléfono"><input value={f.phone} onChange={set('phone')} inputMode="tel" /></Field>
          <Field label="Correo electrónico"><input type="email" value={f.email} onChange={set('email')} /></Field>
        </div>
        <div className="two">
          <Field label="Recibir avisos por">
            <select value={f.preferred_channel} onChange={set('preferred_channel')}>
              {Object.entries(CHANNEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Field>
          <Field label="Comunidad">
            <select value={f.community_id} onChange={set('community_id')}>
              <option value="">Sin comunidad</option>
              {communities.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
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

function AccessModal({ data, onClose }) {
  const [copied, setCopied] = useState(false)
  const text = `Correo: ${data.email}\nContraseña temporal: ${data.temporary_password}`
  async function copy() {
    try { await navigator.clipboard.writeText(text); setCopied(true) } catch { /* sin permiso */ }
  }
  return (
    <Modal title={data.created ? 'Acceso creado' : 'Acceso restablecido'} onClose={onClose}>
      <p className="modal-sub">Entrega estos datos a <strong>{data.name}</strong>. La contraseña temporal solo se muestra ahora;
        se recomienda que la cambie al entrar por primera vez.</p>
      <dl className="creds">
        <dt>Correo</dt><dd>{data.email}</dd>
        <dt>Contraseña temporal</dt><dd><code>{data.temporary_password}</code></dd>
      </dl>
      <div className="modal-actions">
        <button type="button" className="btn ghost" onClick={copy}>{copied ? 'Copiado' : 'Copiar datos'}</button>
        <button type="button" className="btn" onClick={onClose}>Listo</button>
      </div>
    </Modal>
  )
}
