import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { ROLE } from '../utils'

const STAFF_LINKS = [
  { to: '/alertas', label: 'Alertas', badge: true },
  { to: '/ninos', label: 'Niños' },
  { to: '/padres', label: 'Padres de familia' },
  { to: '/comunidades', label: 'Comunidades' },
  { to: '/vacunas', label: 'Catálogo de vacunas' },
]
const MANAGER_LINKS = [
  { to: '/reportes', label: 'Reportes' },
  { to: '/campanas', label: 'Campañas' },
]
const PARENT_LINKS = [{ to: '/mis-ninos', label: 'Mis hijos' }]

export default function Layout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const isParent = user.role === 'parent'
  const isManager = user.role === 'admin' || user.role === 'manager'
  const links = isParent ? PARENT_LINKS : isManager ? [...STAFF_LINKS.slice(0, 1), ...MANAGER_LINKS, ...STAFF_LINKS.slice(1)] : STAFF_LINKS
  const [open, setOpen] = useState(0)

  useEffect(() => {
    if (isParent) return
    api.get('/alerts?status=open').then((a) => setOpen(a.length)).catch(() => {})
  }, [location.pathname, isParent])

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">
          <strong>SCCVI</strong>
          <span>Crecimiento y vacunación infantil</span>
        </div>
        <nav aria-label="Principal">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} className={({ isActive }) => (isActive ? 'active' : '')}>
              {l.label}
              {l.badge && open > 0 && <span className="count" aria-label={`${open} alertas abiertas`}>{open}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="who">
          <span>{user.full_name}</span>
          <small>{ROLE[user.role]}</small>
          <NavLink className="link plain" to="/cuenta">Cambiar contraseña</NavLink>
          <button className="link" onClick={logout}>Cerrar sesión</button>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
