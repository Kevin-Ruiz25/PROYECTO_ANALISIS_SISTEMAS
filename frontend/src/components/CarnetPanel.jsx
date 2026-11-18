import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { ErrorBanner } from './ui'
import { fmtDate } from '../utils'

export default function CarnetPanel({ child }) {
  const [st, setSt] = useState(null)       // { has_carnet, url, qr }
  const [pin, setPin] = useState(null)     // PIN recién emitido (solo se ve una vez)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)

  const load = useCallback(
    () => api.get(`/children/${child.id}/carnet`).then(setSt).catch((e) => setError(e.message)), [child.id])
  useEffect(() => { setPin(null); load() }, [load])

  async function run(fn) {
    setError(''); setBusy(true)
    try { await fn() } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const generate = () => run(async () => {
    const r = await api.post(`/children/${child.id}/carnet`, {})
    setSt({ has_carnet: true, url: r.url, qr: r.qr }); setPin(r.pin)
  })
  const regenerate = () => {
    if (!window.confirm('Se generará un QR y un PIN nuevos. El QR y el PIN anteriores dejarán de funcionar y habrá que imprimir el carnet otra vez. ¿Continuar?')) return
    generate()
  }
  const newPin = () => run(async () => { setPin((await api.post(`/children/${child.id}/carnet/pin`, {})).pin) })
  const revoke = () => {
    if (!window.confirm('Se desactivará el carnet digital de este niño. Los padres ya no podrán abrirlo. ¿Continuar?')) return
    run(async () => { await api.del(`/children/${child.id}/carnet`); setPin(null); await load() })
  }
  const copy = async () => {
    try { await navigator.clipboard.writeText(st.url); setCopied(true); setTimeout(() => setCopied(false), 2000) } catch { /* sin permiso */ }
  }

  if (!st) return error ? <ErrorBanner message={error} /> : <p>Cargando…</p>

  const withAccount = child.parents.filter((p) => p.user_id)
  return (
    <>
      <ErrorBanner message={error} />
      <p className="note first">
        El carnet digital permite a los padres ver las vacunas y los últimos controles de su hijo escaneando un QR.
        Para abrirlo necesitan: iniciar sesión con su cuenta, ser padre o tutor de este niño y escribir un PIN de 6 dígitos.
      </p>

      {child.parents.length === 0 ? (
        <p className="banner warn" role="note">Este niño no tiene padres o tutores asociados. Edita al niño para asociarlos.</p>
      ) : withAccount.length === 0 ? (
        <p className="banner warn" role="note">Ningún padre o tutor tiene cuenta todavía. Créala en la sección Padres de familia
          (botón "Crear acceso") para que puedan abrir el carnet.</p>
      ) : (
        <p className="muted">Pueden abrirlo: {withAccount.map((p) => p.full_name).join(', ')}.</p>
      )}

      {!st.has_carnet ? (
        <div className="empty">
          <strong>Este niño aún no tiene carnet digital</strong>
          <p>Al generarlo se crea un QR único y un PIN de 6 dígitos.</p>
          <button className="btn" onClick={generate} disabled={busy}>{busy ? 'Generando…' : 'Generar carnet digital'}</button>
        </div>
      ) : (
        <>
          {pin && (
            <div className="pin-box" role="status">
              <span>PIN del carnet</span>
              <strong>{pin}</strong>
              <p>Entrégalo al padre o tutor por separado del QR. Por seguridad no se puede volver a consultar; si se pierde, genera un PIN nuevo.</p>
            </div>
          )}

          <div className="carnet-grid">
            <div className="print-area print-card">
              <p className="muted">Carnet digital de vacunación y crecimiento</p>
              <h2>{child.full_name}</h2>
              <p className="muted">Nació el {fmtDate(child.birth_date)}</p>
              <img src={st.qr} alt={`Código QR del carnet de ${child.full_name}`} width="220" height="220" />
              <p className="small">Escanea el código con tu celular, inicia sesión y escribe tu PIN.</p>
            </div>

            <div className="carnet-actions no-print">
              <button className="btn" onClick={() => window.print()}>Imprimir carnet</button>
              <button className="btn ghost" onClick={copy}>{copied ? 'Enlace copiado' : 'Copiar enlace'}</button>
              <button className="btn ghost" onClick={newPin} disabled={busy}>Generar PIN nuevo</button>
              <button className="btn ghost" onClick={regenerate} disabled={busy}>Regenerar QR y PIN</button>
              <button className="btn ghost danger-btn" onClick={revoke} disabled={busy}>Desactivar carnet</button>
              <p className="note">
                "PIN nuevo" sirve si se olvidó el PIN o se bloqueó el acceso; el QR impreso sigue valiendo.
                "Regenerar" es para cuando el QR se perdió o lo vio alguien que no debía.
              </p>
            </div>
          </div>
        </>
      )}
    </>
  )
}
