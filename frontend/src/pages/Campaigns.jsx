import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { ErrorBanner, Field, PageHeader } from '../components/ui'
import { ageLabel } from '../utils'

const VACC = [
  { value: 'con_pendientes', label: 'Con vacunas atrasadas o pendientes' },
  { value: 'atrasadas', label: 'Solo con vacunas atrasadas' },
  { value: 'al_dia', label: 'Con el esquema al día' },
  { value: 'todos', label: 'Todos (sin importar vacunas)' },
]
const AGE_PRESETS = [
  { label: '0 a 2 años', min: 0, max: 23 },
  { label: '2 a 5 años', min: 24, max: 60 },
  { label: '0 a 5 años', min: 0, max: 60 },
]

export default function Campaigns() {
  const [communities, setCommunities] = useState([])
  const [vaccineNames, setVaccineNames] = useState([])
  const [selected, setSelected] = useState([])
  const [ageMin, setAgeMin] = useState(0)
  const [ageMax, setAgeMax] = useState(60)
  const [vaccination, setVaccination] = useState('con_pendientes')
  const [vaccine, setVaccine] = useState('')
  const [preview, setPreview] = useState(null)
  const [title, setTitle] = useState('Jornada de vacunación')
  const [message, setMessage] = useState('Los invitamos a llevar a sus niños al centro de salud para revisar su carnet y completar su esquema de vacunación.')
  const [eventDate, setEventDate] = useState('')
  const [place, setPlace] = useState('')
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState(false)

  useEffect(() => {
    api.get('/communities').then(setCommunities).catch((e) => setError(e.message))
    api.get('/campaigns/vaccine-names').then(setVaccineNames).catch(() => {})
  }, [])

  const filters = () => ({
    community_ids: selected, age_min_months: Number(ageMin), age_max_months: Number(ageMax),
    vaccination, vaccine_name: vaccine || null,
  })
  // al cambiar cualquier filtro, la vista previa y la confirmación ya no valen
  useEffect(() => { setPreview(null); setConfirm(false); setResult(null) }, [selected, ageMin, ageMax, vaccination, vaccine])

  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  async function runPreview() {
    setBusy(true); setError(''); setResult(null)
    try { setPreview(await api.post('/campaigns/preview', filters())) }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  async function send() {
    setBusy(true); setError('')
    try {
      setResult(await api.post('/campaigns/send', {
        ...filters(), title, message, event_date: eventDate || null, place: place || null }))
      setConfirm(false)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const canSend = preview && preview.parents > 0 && title.trim().length >= 3 && message.trim().length >= 10
  return (
    <>
      <PageHeader
        title="Campañas"
        subtitle="Avisa de una vez a los padres de un grupo de niños: por comunidad, edad y estado de vacunación. Cada padre recibe un solo mensaje aunque tenga varios hijos."
      />
      <ErrorBanner message={error} />

      <section className="card">
        <h2>1. ¿A quiénes?</h2>
        <fieldset className="picker">
          <legend>Comunidades (si no marcas ninguna, se incluyen todas)</legend>
          <div className="picker-list tall">
            {communities.map((c) => (
              <label key={c.id}><input type="checkbox" checked={selected.includes(c.id)} onChange={() => toggle(c.id)} /> {c.name}</label>
            ))}
            {communities.length === 0 && <small>Aún no hay comunidades registradas.</small>}
          </div>
        </fieldset>

        <div className="two">
          <Field label="Edad mínima (meses)"><input type="number" min="0" max="216" value={ageMin} onChange={(e) => setAgeMin(e.target.value)} /></Field>
          <Field label="Edad máxima (meses)"><input type="number" min="0" max="216" value={ageMax} onChange={(e) => setAgeMax(e.target.value)} /></Field>
        </div>
        <div className="chips" aria-label="Rangos de edad rápidos">
          {AGE_PRESETS.map((p) => (
            <button key={p.label} type="button" className="chip" onClick={() => { setAgeMin(p.min); setAgeMax(p.max) }}>{p.label}</button>
          ))}
        </div>

        <div className="two">
          <Field label="Estado de vacunación">
            <select value={vaccination} onChange={(e) => setVaccination(e.target.value)}>
              {VACC.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
            </select>
          </Field>
          <Field label="Vacuna específica" hint="Opcional: revisa solo esta vacuna (por ejemplo, una campaña de SPR).">
            <select value={vaccine} onChange={(e) => setVaccine(e.target.value)}>
              <option value="">Cualquier vacuna</option>
              {vaccineNames.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </Field>
        </div>
        <button className="btn" onClick={runPreview} disabled={busy}>{busy && !preview ? 'Calculando…' : 'Ver a quiénes alcanza'}</button>

        {preview && (
          <div className="preview" role="status">
            <p>
              <strong>{preview.children}</strong> niños · <strong>{preview.parents}</strong> padres o tutores
              {preview.parents > 0 && <> · <strong>{preview.with_email}</strong> con correo</>}
            </p>
            {preview.without_contact > 0 && <p className="muted">{preview.without_contact} padres no tienen correo; su aviso quedará registrado como «sin contacto» para avisarles en persona.</p>}
            {preview.children_without_parents > 0 && <p className="muted">{preview.children_without_parents} niños no tienen padre o tutor asociado y no recibirán aviso.</p>}
            {preview.sample.length > 0 && (
              <details>
                <summary>Ver niños incluidos{preview.children > preview.sample.length ? ` (primeros ${preview.sample.length})` : ''}</summary>
                <ul className="plain-list">
                  {preview.sample.map((s) => (
                    <li key={s.child_id}><Link className="name-link" to={`/ninos/${s.child_id}`}>{s.name}</Link>
                      {' '}— {s.community}, {s.age_months < 24 ? `${s.age_months} meses` : `${Math.floor(s.age_months / 12)} años`}
                      {s.doses_overdue > 0 && `, ${s.doses_overdue} dosis atrasadas`}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
      </section>

      <section className="card">
        <h2>2. ¿Qué les decimos?</h2>
        <Field label="Asunto"><input value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} /></Field>
        <Field label="Mensaje" hint="Se le antepone «Hola, nombre del padre» y se agregan los nombres de sus niños."><textarea rows={4} maxLength={1500} value={message} onChange={(e) => setMessage(e.target.value)} /></Field>
        <div className="two">
          <Field label="Fecha (opcional)"><input type="date" value={eventDate} onChange={(e) => setEventDate(e.target.value)} /></Field>
          <Field label="Lugar (opcional)"><input value={place} maxLength={200} onChange={(e) => setPlace(e.target.value)} placeholder="Salón comunal" /></Field>
        </div>

        {result ? (
          <p className="banner info" role="status">
            Campaña enviada a {result.parents} padres ({result.children} niños).
            {result.envio.enviadas + result.envio.simuladas > 0 && ` Correos enviados: ${result.envio.enviadas + result.envio.simuladas}.`}
            {result.envio.pendientes > 0 && ` ${result.envio.pendientes} quedan pendientes porque el correo no está configurado.`}
            {result.envio.errores > 0 && ` ${result.envio.errores} con error (${result.envio.ultimo_error}).`}
            {result.without_contact > 0 && ` ${result.without_contact} sin correo registrado.`}
            {' '}Puedes verlos en <Link to="/alertas">Alertas → Notificaciones a padres</Link>.
          </p>
        ) : !confirm ? (
          <button className="btn" disabled={!canSend || busy} onClick={() => setConfirm(true)}>Enviar campaña</button>
        ) : (
          <div className="confirm" role="alertdialog" aria-label="Confirmar envío">
            <p>Se enviará «{title}» a <strong>{preview.parents}</strong> padres. Esto no se puede deshacer.</p>
            <div className="btn-row">
              <button className="btn" onClick={send} disabled={busy}>{busy ? 'Enviando…' : 'Sí, enviar ahora'}</button>
              <button className="btn ghost" onClick={() => setConfirm(false)} disabled={busy}>Cancelar</button>
            </div>
          </div>
        )}
        {!preview && !result && <p className="muted">Primero usa «Ver a quiénes alcanza» para comprobar el grupo.</p>}
      </section>
    </>
  )
}
