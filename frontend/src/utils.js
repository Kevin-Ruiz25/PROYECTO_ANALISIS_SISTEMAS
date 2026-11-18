export function ageLabel(iso) {
  const b = new Date(iso)
  const n = new Date()
  let m = (n.getFullYear() - b.getFullYear()) * 12 + n.getMonth() - b.getMonth()
  if (n.getDate() < b.getDate()) m--
  if (m < 0) m = 0
  if (m < 24) return `${m} ${m === 1 ? 'mes' : 'meses'}`
  const y = Math.floor(m / 12)
  const r = m % 12
  return r ? `${y} años ${r} m` : `${y} años`
}

export const SEX = { M: 'Masculino', F: 'Femenino' }
export const CHANNEL = { email: 'Correo', telegram: 'Telegram', whatsapp: 'WhatsApp' }
export const ROLE = {
  admin: 'Administrador',
  health_staff: 'Personal de salud',
  manager: 'Encargado del centro',
  parent: 'Padre de familia',
}
export const todayISO = () => {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

// Formato de percentil: "P23", "<1", ">99"
export function pctLabel(p) {
  if (p === null || p === undefined) return '—'
  if (p < 1) return 'P<1'
  if (p > 99) return 'P>99'
  return 'P' + Math.round(p)
}

// Orientación según los umbrales del proyecto (P5 y P95). Es una guía, no un diagnóstico.
export function growthStatus(kind, p) {
  if (p === null || p === undefined) return null
  if (kind === 'weight') {
    if (p < 5) return { text: 'Peso bajo', tone: 'danger' }
    if (p > 95) return { text: 'Peso alto', tone: 'warn' }
  } else {
    if (p < 5) return { text: 'Talla baja', tone: 'warn' }
    if (p > 95) return { text: 'Talla alta', tone: 'info' }
  }
  return { text: 'Esperado', tone: 'ok' }
}

// ---- Vacunación
export function fmtDate(iso) {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

export function monthsLabel(m) {
  if (m === 0) return 'Al nacer'
  if (m < 24) return `${m} ${m === 1 ? 'mes' : 'meses'}`
  const y = Math.floor(m / 12)
  const r = m % 12
  return r ? `${y} años ${r} m` : `${y} ${y === 1 ? 'año' : 'años'}`
}

export const VAX_STATUS = {
  completa: { text: 'Completa', tone: 'ok' },
  atrasada: { text: 'Atrasada', tone: 'danger' },
  pendiente: { text: 'Pendiente', tone: 'warn' },
  proxima: { text: 'Aún no toca', tone: 'muted' },
}

// ---- Alertas y notificaciones
export const REASON = {
  peso_bajo: 'Peso bajo',
  peso_alto: 'Peso alto',
  sin_controles: 'Sin controles',
  vacunas_atrasadas: 'Vacunas atrasadas',
}
export const ALERT_TYPE = {
  critica: { text: 'Crítica', tone: 'danger' },
  preventiva: { text: 'Preventiva', tone: 'warn' },
}
export const NOTIF_STATUS = {
  enviada: { text: 'Enviada', tone: 'ok' },
  simulada: { text: 'Simulada (consola)', tone: 'info' },
  pendiente: { text: 'Pendiente de envío', tone: 'warn' },
  error: { text: 'Error al enviar', tone: 'danger' },
  sin_contacto: { text: 'Sin correo registrado', tone: 'muted' },
  canal_no_disponible: { text: 'Canal no disponible', tone: 'muted' },
}
export const MAIL_MODE_TEXT = {
  smtp: null,
  console: 'El correo está en modo de demostración: los mensajes se imprimen en la terminal del backend y no se envían.',
  none: 'El correo no está configurado: las notificaciones quedan pendientes hasta configurar SMTP_HOST en el backend.',
}
export function fmtDateTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z')
  return d.toLocaleString('es-GT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// ---- Reportes
export function fmtCell(value, kind) {
  if (value === null || value === undefined || value === '') return '—'
  if (kind === 'date') return new Date(value + 'T00:00:00').toLocaleDateString('es-GT')
  if (kind === 'float') return Number(value).toFixed(1)
  return String(value)
}
