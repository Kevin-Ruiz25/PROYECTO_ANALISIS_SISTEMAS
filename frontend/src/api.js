const BASE = '/api'

export const getToken = () => localStorage.getItem('token')

function errorMessage(data, status) {
  const d = data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) {
    return 'Revisa los datos: ' + d.map((e) => `${e.loc?.slice(1).join('.') || 'campo'} (${e.msg})`).join('; ')
  }
  return `Error ${status}. Intenta de nuevo.`
}

async function request(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let payload
  if (form) {
    payload = new URLSearchParams(form)
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
  } else if (body !== undefined) {
    payload = JSON.stringify(body)
    headers['Content-Type'] = 'application/json'
  }

  let res
  try {
    res = await fetch(BASE + path, { method, headers, body: payload })
  } catch {
    throw new Error('No hay conexión con el servidor. Verifica que el backend esté en ejecución.')
  }

  if (res.status === 401 && token) {
    localStorage.removeItem('token')
    window.dispatchEvent(new Event('auth:expired'))
  }
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new Error(errorMessage(data, res.status))
  return data
}

// Descarga un archivo (Excel/PDF) con el token, porque un enlace normal no enviaría la sesión.
async function download(path) {
  const token = getToken()
  let res
  try {
    res = await fetch(BASE + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  } catch {
    throw new Error('No hay conexión con el servidor. Verifica que el backend esté en ejecución.')
  }
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(errorMessage(data, res.status))
  }
  const name = /filename="?([^";]+)"?/.exec(res.headers.get('Content-Disposition') || '')?.[1] || 'reporte'
  const url = URL.createObjectURL(await res.blob())
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const api = {
  download,
  login: (email, password) => request('/auth/login', { method: 'POST', form: { username: email, password } }),
  me: () => request('/auth/me'),
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body }),
  put: (path, body) => request(path, { method: 'PUT', body }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  del: (path) => request(path, { method: 'DELETE' }),
}
