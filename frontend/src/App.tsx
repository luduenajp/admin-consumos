import { useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import './App.css'
import { ErrorBoundary } from './components/ErrorBoundary'
import { AdminPage } from './pages/admin-page'
import { DashboardPage } from './pages/dashboard-page'
import { ImportPage } from './pages/import-page'
import { PurchasesPage } from './pages/purchases-page'
import { BudgetPage } from './pages/budget-page'
import { CategoriesPage } from './pages/categories-page'
import { GoalsPage } from './pages/goals-page'
import { SavingsPage } from './pages/savings-page'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/purchases', label: 'Compras' },
  { to: '/import', label: 'Importar' },
  { to: '/budget', label: 'Presupuesto' },
  { to: '/ahorros', label: 'Ahorros' },
  { to: '/categories', label: 'Categorías' },
  { to: '/goals', label: 'Objetivos' },
  { to: '/admin', label: 'Admin' },
]

function App() {
  const [menuOpen, setMenuOpen] = useState(false)
  const closeMenu = () => setMenuOpen(false)

  return (
    <div className="appShell">
      <header className="appHeader">
        <div className="appTitle">Admin Consumos</div>

        <nav className="appNav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              className={({ isActive }) => (isActive ? 'appLink active' : 'appLink')}
              to={item.to}
              end={item.end}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <button
          className={`menuToggle${menuOpen ? ' open' : ''}`}
          onClick={() => setMenuOpen((o) => !o)}
          aria-label="Menú"
          aria-expanded={menuOpen}
        >
          <span />
          <span />
          <span />
        </button>
      </header>

      {menuOpen && (
        <>
          <div className="mobileMenuOverlay" onClick={closeMenu} />
          <nav className="mobileMenu">
            <div className="mobileMenuHeader">
              <div className="appTitle">Admin Consumos</div>
              <button className="mobileMenuClose" onClick={closeMenu} aria-label="Cerrar">✕</button>
            </div>
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                className={({ isActive }) => (isActive ? 'mobileLink active' : 'mobileLink')}
                to={item.to}
                end={item.end}
                onClick={closeMenu}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </>
      )}

      <main className="appMain">
        <ErrorBoundary>
          <Routes>
            <Route element={<DashboardPage />} path="/" />
            <Route element={<PurchasesPage />} path="/purchases" />
            <Route element={<ImportPage />} path="/import" />
            <Route element={<BudgetPage />} path="/budget" />
            <Route element={<CategoriesPage />} path="/categories" />
            <Route element={<GoalsPage />} path="/goals" />
            <Route element={<SavingsPage />} path="/ahorros" />
            <Route element={<AdminPage />} path="/admin" />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  )
}

export default App
