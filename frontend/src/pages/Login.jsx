import { useState } from 'react'
import { useAuth } from '../auth'
import { ErrorBanner, Field } from '../components/ui'

// Curvas decorativas: recuerdan las líneas de percentiles de una gráfica de crecimiento
function Curves() {
  const curve = (k) => `M0 ${300 - 20 * k} C 120 ${290 - 60 * k}, 220 ${200 - 55 * k}, 400 ${60 - 20 * k}`
  return (
    <svg viewBox="0 0 400 300" className="curves" aria-hidden="true">
      {[0, 1, 2, 3, 4].map((k) => (
        <path key={k} d={curve(k)} className={k === 2 ? 'p50' : ''} />
      ))}
      <circle cx="250" cy="150" r="7" />
    </svg>
  )
}

export default function Login() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(email.trim(), password)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <section className="login-art">
        <Curves />
        <h1>Cada control cuenta</h1>
        <p>Peso, talla y vacunas de los niños de tu comunidad, en un solo lugar.</p>
      </section>
      <section className="login-form">
        <form onSubmit={submit}>
          <h2>Iniciar sesión</h2>
          <ErrorBanner message={error} />
          <Field label="Correo electrónico">
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          </Field>
          <Field label="Contraseña">
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </Field>
          <button className="btn" disabled={busy}>{busy ? 'Entrando…' : 'Entrar'}</button>
        </form>
      </section>
    </div>
  )
}
