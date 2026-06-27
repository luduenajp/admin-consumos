import { lazy, Suspense, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import './App.css'
import { ErrorBoundary } from './components/ErrorBoundary'

// Lazy-loaded por ruta: cada página es su propio chunk y las libs pesadas
// (recharts) se descargan solo al entrar a las páginas que las usan.
const AdminPage = lazy(() => import('./pages/admin-page').then((m) => ({ default: m.AdminPage })))
const DashboardPage = lazy(() => import('./pages/dashboard-page').then((m) => ({ default: m.DashboardPage })))
const ImportPage = lazy(() => import('./pages/import-page').then((m) => ({ default: m.ImportPage })))
const PurchasesPage = lazy(() => import('./pages/purchases-page').then((m) => ({ default: m.PurchasesPage })))
const BudgetPage = lazy(() => import('./pages/budget-page').then((m) => ({ default: m.BudgetPage })))
const CategoriesPage = lazy(() => import('./pages/categories-page').then((m) => ({ default: m.CategoriesPage })))
const GoalsPage = lazy(() => import('./pages/goals-page').then((m) => ({ default: m.GoalsPage })))
const SavingsPage = lazy(() => import('./pages/savings-page').then((m) => ({ default: m.SavingsPage })))
const GastosCategoriaPage = lazy(() =>
  import('./pages/gastos-categorias-page').then((m) => ({ default: m.GastosCategoriaPage })),
)
const NuevaTransferenciaPage = lazy(() =>
  import('./pages/nueva-transferencia-page').then((m) => ({ default: m.NuevaTransferenciaPage })),
)
const ServiciosPage = lazy(() =>
  import('./pages/servicios-page').then((m) => ({ default: m.ServiciosPage })),
)

type NavItem = { to: string; label: string; icon: string; end?: boolean; mobileHide?: boolean }

const NAV_GROUPS: { label: string; secondary: boolean; items: NavItem[] }[] = [
  {
    label: 'Principal',
    secondary: false,
    items: [
      { to: '/', label: 'Dashboard', icon: '📊', end: true },
      { to: '/gastos-categorias', label: 'Categorías', icon: '📊' },
      { to: '/import', label: 'Importar', icon: '📥' },
      { to: '/servicios', label: 'Servicios', icon: '🧾' },
      { to: '/admin', label: 'Admin', icon: '⚙️' },
    ],
  },
  {
    label: 'Más',
    secondary: true,
    items: [
      { to: '/budget', label: 'Presupuesto', icon: '💰', mobileHide: true },
      { to: '/ahorros', label: 'Ahorros', icon: '🐖' },
      { to: '/categories', label: 'Categorías', icon: '🏷️' },
      { to: '/goals', label: 'Objetivos', icon: '🎯' },
    ],
  },
]

const NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items)

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
              <div className="appTitle mobileMenuTitle">Admin Consumos</div>
              <button className="mobileMenuClose" onClick={closeMenu} aria-label="Cerrar">✕</button>
            </div>
            <div className="mobileMenuContent">
              {NAV_GROUPS.map((group) => (
                <div key={group.label} className="mobileMenuGroup">
                  <div className="mobileMenuGroupLabel">{group.label}</div>
                  {group.items.filter((item) => !item.mobileHide).map((item) => (
                    <NavLink
                      key={item.to}
                      className={({ isActive }) =>
                        ['mobileLink', group.secondary ? 'mobileLinkSecondary' : '', isActive ? 'active' : '']
                          .filter(Boolean)
                          .join(' ')
                      }
                      to={item.to}
                      end={item.end}
                      onClick={closeMenu}
                    >
                      <span className="mobileLinkIcon">{item.icon}</span>
                      <span>{item.label}</span>
                    </NavLink>
                  ))}
                </div>
              ))}
            </div>
          </nav>
        </>
      )}

      <main className="appMain">
        <ErrorBoundary>
          <Suspense fallback={<div className="muted" style={{ padding: '2rem' }}>Cargando…</div>}>
            <Routes>
              <Route element={<DashboardPage />} path="/" />
              <Route element={<GastosCategoriaPage />} path="/gastos-categorias" />
              <Route element={<PurchasesPage />} path="/purchases" />
              <Route element={<ImportPage />} path="/import" />
              <Route element={<BudgetPage />} path="/budget" />
              <Route element={<CategoriesPage />} path="/categories" />
              <Route element={<GoalsPage />} path="/goals" />
              <Route element={<SavingsPage />} path="/ahorros" />
              <Route element={<NuevaTransferenciaPage />} path="/nueva-transferencia" />
              <Route element={<ServiciosPage />} path="/servicios" />
              <Route element={<AdminPage />} path="/admin" />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </main>
    </div>
  )
}

export default App
