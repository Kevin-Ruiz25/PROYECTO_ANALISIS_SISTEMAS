import { useState } from 'react'
import { api } from '../api'
import { ErrorBanner, Field, PageHeader } from '../components/ui'

export default function Account() {
  const [f, setF] = useState({ current: '', next: '', again: '' })
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    setError(''); setDone(false)
    if (f.next.length < 8) return setError('La contraseña nueva debe tener al menos 8 caracteres.')
    if (f.next !== f.again) return setError('La confirmación no coincide con la contraseña nueva.')
    setBusy(true)
    try {
      await api.post('/auth/change-password', { current_password: f.current, new_password: f.next })
      setF({ current: '', next: '', again: '' })
      setDone(true)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <>
      <PageHeader title="Cambiar contraseña" subtitle="Usa una contraseña que solo tú conozcas." />
      <form className="card narrow" onSubmit={submit}>
        <ErrorBanner message={error} />
        {done && <p className="banner ok" role="status">Contraseña actualizada.</p>}
        <Field label="Contraseña actual">
          <input type="password" value={f.current} onChange={set('current')} required autoComplete="current-password" />
        </Field>
        <Field label="Contraseña nueva" hint="Mínimo 8 caracteres.">
          <input type="password" value={f.next} onChange={set('next')} required minLength={8} autoComplete="new-password" />
        </Field>
        <Field label="Repite la contraseña nueva">
          <input type="password" value={f.again} onChange={set('again')} required autoComplete="new-password" />
        </Field>
        <button className="btn" disabled={busy}>{busy ? 'Guardando…' : 'Guardar contraseña'}</button>
      </form>
    </>
  )
}
