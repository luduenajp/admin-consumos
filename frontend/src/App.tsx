import { NavLink, Route, Routes } from 'react-router-dom'
import './App.css'
import { ErrorBoundary } from './components/ErrorBoundary'
import { AdminPage } from './pages/admin-page'
import { DashboardPage } from './pages/dashboard-page'
import { ImportPage } from './pages/import-page'
import { PurchasesPage } from './pages/purchases-page'

function App() {
  return (
    <div className="appShell">
      <header className="appHeader">
        <div className="appTitle">Admin Consumos</div>
        <nav className="appNav">
          <NavLink className={({ isActive }) => (isActive ? 'appLink active' : 'appLink')} to="/">
            Dashboard
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? 'appLink active' : 'appLink')} to="/purchases">
            Compras
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? 'appLink active' : 'appLink')} to="/import">
            Importar
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? 'appLink active' : 'appLink')} to="/admin">
            Admin
          </NavLink>
        </nav>
      </header>

      <main className="appMain">
        <ErrorBoundary>
          <Routes>
            <Route element={<DashboardPage />} path="/" />
            <Route element={<PurchasesPage />} path="/purchases" />
            <Route element={<ImportPage />} path="/import" />
            <Route element={<AdminPage />} path="/admin" />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  )
}

export default App
