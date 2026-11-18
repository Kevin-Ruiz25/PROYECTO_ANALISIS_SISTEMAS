import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import Login from './pages/Login'
import Children from './pages/Children'
import ChildDetail from './pages/ChildDetail'
import Parents from './pages/Parents'
import Communities from './pages/Communities'
import Vaccines from './pages/Vaccines'
import Alerts from './pages/Alerts'
import MyChildren from './pages/MyChildren'
import CarnetView from './pages/CarnetView'
import Account from './pages/Account'
import Reports from './pages/Reports'
import Campaigns from './pages/Campaigns'

const homeFor = (user) => (user.role === 'parent' ? '/mis-ninos' : '/alertas')

function Protected({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <p className="center-note">Cargando…</p>
  // se recuerda a dónde iba (p. ej. al escanear un QR) para volver tras iniciar sesión
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  return children
}

function StaffOnly({ children }) {
  const { user } = useAuth()
  return user.role === 'parent' ? <Navigate to="/mis-ninos" replace /> : children
}

function ManagerOnly({ children }) {
  const { user } = useAuth()
  return user.role === 'admin' || user.role === 'manager' ? children : <Navigate to={homeFor(user)} replace />
}

function ParentOnly({ children }) {
  const { user } = useAuth()
  return user.role === 'parent' ? children : <Navigate to={homeFor(user)} replace />
}

function LoginRoute() {
  const { user } = useAuth()
  const location = useLocation()
  if (!user) return <Login />
  const from = location.state?.from
  return <Navigate to={from ? from.pathname + (from.search || '') : homeFor(user)} replace />
}

function Home() {
  const { user } = useAuth()
  return <Navigate to={homeFor(user)} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route path="/alertas" element={<StaffOnly><Alerts /></StaffOnly>} />
        <Route path="/ninos" element={<StaffOnly><Children /></StaffOnly>} />
        <Route path="/ninos/:id" element={<StaffOnly><ChildDetail /></StaffOnly>} />
        <Route path="/padres" element={<StaffOnly><Parents /></StaffOnly>} />
        <Route path="/comunidades" element={<StaffOnly><Communities /></StaffOnly>} />
        <Route path="/reportes" element={<ManagerOnly><Reports /></ManagerOnly>} />
        <Route path="/campanas" element={<ManagerOnly><Campaigns /></ManagerOnly>} />
        <Route path="/vacunas" element={<StaffOnly><Vaccines /></StaffOnly>} />
        <Route path="/mis-ninos" element={<ParentOnly><MyChildren /></ParentOnly>} />
        <Route path="/carnet/:token" element={<CarnetView />} />
        <Route path="/cuenta" element={<Account />} />
      </Route>
      <Route path="*" element={<Protected><Home /></Protected>} />
    </Routes>
  )
}
