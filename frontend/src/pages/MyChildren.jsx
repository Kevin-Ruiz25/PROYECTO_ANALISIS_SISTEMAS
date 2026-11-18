import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Empty, ErrorBanner, PageHeader } from '../components/ui'
import { ageLabel, fmtDate } from '../utils'

export default function MyChildren() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { api.get('/me/children').then(setItems).catch((e) => setError(e.message)) }, [])

  return (
    <>
      <PageHeader title="Mis hijos" subtitle="Abre el carnet digital de vacunación y crecimiento de cada niño." />
      <ErrorBanner message={error} />
      {items === null ? <p>Cargando…</p> : items.length === 0 ? (
        <Empty title="Aún no hay niños asociados a tu cuenta"
          text="Pide en el centro de salud que asocien a tus hijos con tu registro." />
      ) : (
        <div className="kids">
          {items.map((c) => (
            <article key={c.child_id} className="card kid">
              <h2>{c.full_name}</h2>
              <p className="muted">{ageLabel(c.birth_date)} · nació el {fmtDate(c.birth_date)}</p>
              {c.has_carnet
                ? <Link className="btn" to={`/carnet/${c.token}`}>Abrir carnet</Link>
                : <p className="muted">Su carnet digital aún no está disponible. Solicítalo en el centro de salud.</p>}
            </article>
          ))}
        </div>
      )}
    </>
  )
}
