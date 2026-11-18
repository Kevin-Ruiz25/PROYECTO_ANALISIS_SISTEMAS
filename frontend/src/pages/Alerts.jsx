import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Empty, ErrorBanner, PageHeader } from '../components/ui'
import { ALERT_TYPE, MAIL_MODE_TEXT, NOTIF_STATUS, REASON, fmtDateTime } from '../utils'

export default function Alerts() {
  const [tab, setTab] = useState('alertas')
  const [status, setStatus] = useState('open')
  const [type, setType] = useState('')
  const [alerts, setAlerts] = useState(null)
  const [notifs, setNotifs] = useState(null)
  const [mailMode, setMailMode] = useState('smtp')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [busy, setBusy] = useState(false)

  const loadAlerts = useCallback(() => {
    const p = new URLSearchParams({ status })
    if (type) p.set('type', type)
    return api.get('/alerts?' + p).then(setAlerts).catch((e) => setError(e.message))
  }, [status, type])
  const loadNotifs = useCallback(
    () => api.get('/notifications').then(setNotifs).catch((e) => setError(e.message)), [])

  useEffect(() => { loadAlerts() }, [loadAlerts])
  useEffect(() => { loadNotifs(); api.get('/mail/status').then((m) => setMailMode(m.mode)).catch(() => {}) }, [loadNotifs])

  async function evaluate() {
    setBusy(true); setError(''); setInfo('')
    try {
      const r = await api.post('/alerts/evaluate', {})
      setInfo(`Se revisaron ${r.children} niños: ${r.created} alertas nuevas, ${r.resolved} resueltas y ${r.notifications} notificaciones generadas.`)
      await Promise.all([loadAlerts(), loadNotifs()])
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  async function retry() {
    setBusy(true); setError(''); setInfo('')
    try {
      const r = await api.post('/notifications/dispatch', {})
      const sent = r.enviadas + r.simuladas
      setInfo(r.pendientes
        ? `${r.pendientes} notificaciones siguen pendientes porque el correo no está configurado.`
        : `Envío terminado: ${sent} enviadas${r.errores ? `, ${r.errores} con error (${r.ultimo_error})` : ''}.`)
      await loadNotifs()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const critical = (alerts || []).filter((a) => a.type === 'critica').length
  const toRetry = (notifs || []).filter((n) => n.status === 'pendiente' || n.status === 'error').length

  return (
    <>
      <PageHeader
        title="Alertas"
        subtitle="Niños que necesitan atención según peso, controles y vacunas. Se cierran solas cuando el problema se resuelve."
        action={<button className="btn" onClick={evaluate} disabled={busy}>{busy ? 'Revisando…' : 'Revisar todos los niños'}</button>}
      />
      <ErrorBanner message={error} />
      {info && <p className="banner info" role="status">{info}</p>}
      {MAIL_MODE_TEXT[mailMode] && <p className="banner warn" role="note">{MAIL_MODE_TEXT[mailMode]}</p>}

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'alertas'} className={tab === 'alertas' ? 'on' : ''} onClick={() => setTab('alertas')}>Alertas</button>
        <button role="tab" aria-selected={tab === 'notif'} className={tab === 'notif' ? 'on' : ''} onClick={() => setTab('notif')}>Notificaciones a padres</button>
      </div>

      {tab === 'alertas' && (
        <>
          <div className="filters two-sel">
            <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Estado">
              <option value="open">Abiertas</option>
              <option value="resolved">Resueltas</option>
              <option value="all">Todas</option>
            </select>
            <select value={type} onChange={(e) => setType(e.target.value)} aria-label="Tipo">
              <option value="">Todos los tipos</option>
              <option value="critica">Críticas</option>
              <option value="preventiva">Preventivas</option>
            </select>
          </div>
          {alerts === null ? <p>Cargando…</p> : alerts.length === 0 ? (
            <Empty title={status === 'open' ? 'No hay alertas abiertas' : 'No hay alertas con estos filtros'}
              text="Las alertas aparecen al registrar mediciones y vacunas, y en la revisión diaria. También puedes revisar todos los niños ahora." />
          ) : (
            <>
              {status === 'open' && <p className="muted">{alerts.length} abiertas, {critical} críticas.</p>}
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Tipo</th><th>Niño</th><th>Motivo</th><th>Detalle</th><th>Comunidad</th><th>Desde</th></tr></thead>
                  <tbody>
                    {alerts.map((a) => {
                      const t = ALERT_TYPE[a.type]
                      return (
                        <tr key={a.id}>
                          <td><span className={`badge ${t.tone}`}>{t.text}</span></td>
                          <td><Link className="name-link" to={`/ninos/${a.child_id}`}>{a.child_name}</Link></td>
                          <td>{REASON[a.reason] || a.reason}{a.resolved && <span className="badge ok tag">Resuelta</span>}</td>
                          <td className="wrap">{a.message}</td>
                          <td>{a.community_name || '—'}</td>
                          <td>{fmtDateTime(a.created_at)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}

      {tab === 'notif' && (
        <>
          <div className="toolbar">
            <p className="muted">Avisos generados para los padres o tutores. Se envía por correo cuando el padre tiene uno registrado; Telegram y WhatsApp llegan en un paso posterior.</p>
            {toRetry > 0 && <button className="btn ghost" onClick={retry} disabled={busy}>Reintentar envío ({toRetry})</button>}
          </div>
          {notifs === null ? <p>Cargando…</p> : notifs.length === 0 ? (
            <Empty title="Aún no hay notificaciones" text="Se crean cuando se abre una alerta de un niño que tiene padres o tutores asociados." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Padre o tutor</th><th>Niño</th><th>Asunto</th><th>Canal</th><th>Estado</th><th>Enviada</th></tr></thead>
                <tbody>
                  {notifs.map((n) => {
                    const s = NOTIF_STATUS[n.status] || { text: n.status, tone: 'muted' }
                    return (
                      <tr key={n.id}>
                        <td>{n.parent_name}</td>
                        <td>{n.child_id ? <Link className="name-link" to={`/ninos/${n.child_id}`}>{n.child_name}</Link> : '—'}</td>
                        <td className="wrap">{n.subject}</td>
                        <td>{n.channel === 'email' ? 'Correo' : n.channel === 'telegram' ? 'Telegram' : 'WhatsApp'}</td>
                        <td><span className={`badge ${s.tone}`}>{s.text}</span></td>
                        <td>{fmtDateTime(n.sent_at)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </>
  )
}
