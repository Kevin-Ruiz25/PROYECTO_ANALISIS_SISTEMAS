import { useEffect, useState } from 'react'
import { api } from '../api'
import { ALERT_TYPE, REASON } from '../utils'

// Alertas abiertas de un niño. `refreshKey` cambia cuando se registra una medición o una vacuna.
export default function ChildAlerts({ childId, refreshKey }) {
  const [items, setItems] = useState([])

  useEffect(() => {
    api.get(`/alerts?status=open&child_id=${childId}`).then(setItems).catch(() => setItems([]))
  }, [childId, refreshKey])

  if (items.length === 0) return null
  return (
    <section className="child-alerts" aria-label="Alertas del niño">
      {items.map((a) => {
        const t = ALERT_TYPE[a.type]
        return (
          <div key={a.id} className={`alert-row ${t.tone}`} role="status">
            <span className={`badge ${t.tone}`}>{t.text}</span>
            <div>
              <strong>{REASON[a.reason] || a.reason}</strong>
              <p>{a.message}</p>
            </div>
          </div>
        )
      })}
    </section>
  )
}
