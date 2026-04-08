import { useState } from 'react'
import usePatients from './hooks/usePatients'
import useTrend    from './hooks/useTrend'
import KpiCards       from './components/KpiCards'
import RiskChart      from './components/RiskChart'
import PatientTable   from './components/PatientTable'
import PatientDrawer  from './components/PatientDrawer'
import ScheduleModal  from './components/ScheduleModal'
import MLInsights     from './components/MLInsights'
import Interventions  from './components/Interventions'

// Inject Chart.js once
if (!window._chartJsLoaded) {
  window._chartJsLoaded = true
  const s = document.createElement('script')
  s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'
  document.head.appendChild(s)
}

const NAV = [
  { icon: '⬛', label: 'Dashboard'                    },
  { icon: '👥', label: 'Patients',      pill: 'live'  },
  { divider: 'CLINICAL' },
  { icon: '⚡', label: 'Risk Engine'                  },
  { icon: '🔔', label: 'Interventions', pill: 'alert', pillWarn: true },
  { icon: '📤', label: 'Schedule',      action: 'schedule' },
]

export default function App() {
  const { patients, stats, loading, error } = usePatients()
  const trend = useTrend()

  const [selected,    setSelected]    = useState(null)
  const [scheduleFor, setScheduleFor] = useState(null)
  const [collapsed,   setCollapsed]   = useState(false)
  const [activeNav,   setActiveNav]   = useState('Dashboard')
  const [search,      setSearch]      = useState('')
  const [toast,       setToast]       = useState('')

  function showToast(msg) {
    setToast(msg)
    setTimeout(() => setToast(''), 3200)
  }

  function openScheduleFor(p) {
    setSelected(null)
    setScheduleFor(p)
  }

  const visiblePatients = search
    ? patients.filter(p => {
        const q = search.toLowerCase()
        return (
          (p.name    || '').toLowerCase().includes(q) ||
          (p.disease || '').toLowerCase().includes(q) ||
          (p.doctor  || '').toLowerCase().includes(q)
        )
      })
    : patients

  // Decide which main view to render
  const showML            = activeNav === 'Risk Engine'
  const showInterventions = activeNav === 'Interventions'

  return (
    <div className="app">
      {/* ── SIDEBAR ── */}
      <nav className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
        <div className="logo">
          <div className="logo-mark">H</div>
          {!collapsed && <span className="logo-name">HEALo</span>}
        </div>

        <div className="nav-scroll">
          {NAV.map((n, i) => {
            if (n.divider) return !collapsed
              ? <div key={i} className="nav-group-label">{n.divider}</div>
              : <div key={i} style={{ height: 8 }} />
            return (
              <div key={i}
                className={`nav-item ${activeNav === n.label ? 'active' : ''}`}
                onClick={() => {
                  setActiveNav(n.label)
                  if (n.action === 'schedule') setScheduleFor(patients[0] || null)
                }}>
                <span className="nav-icon">{n.icon}</span>
                {!collapsed && <span className="nav-text">{n.label}</span>}
                {!collapsed && n.pill && (
                  <span className={`nav-pill ${n.pillWarn ? 'warn' : ''}`}>
                    {n.pill === 'live'  ? patients.length || '…'
                     : n.pill === 'alert' ? (stats?.high_risk ?? '…')
                     : n.pill}
                  </span>
                )}
              </div>
            )
          })}
        </div>

        <div className="sidebar-footer">
          <div className="u-row">
            <div className="u-avatar">BN</div>
            {!collapsed && (
              <div>
                <div className="u-name">Bhavana Nair</div>
                <div className="u-role">Admin · Chennai</div>
              </div>
            )}
          </div>
        </div>
      </nav>

      {/* ── MAIN ── */}
      <div className="main">
        <header className="topbar">
          <button className="icon-btn" onClick={() => setCollapsed(c => !c)} title="Toggle sidebar">
            ☰
          </button>
          <span className="topbar-title">
            {showML            ? 'Model Intelligence — FL · RL · XGBoost'
             : showInterventions ? 'Interventions — Escalations & Silent Patients'
             : 'Patient Intelligence Dashboard'}
          </span>

          <div className="topbar-right">
            <div className="search-wrap">
              <span className="search-icon">🔍</span>
              <input
                placeholder="Search patients…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
            <button
              className="icon-btn"
              title="Schedule message"
              onClick={() => setScheduleFor(patients[0] || null)}>
              📤
            </button>
          </div>
        </header>

        <main className="content">
          {error && (
            <div style={{ background: 'var(--hibg)', color: 'var(--hi)', padding: '10px 16px', borderRadius: 'var(--r3)', fontSize: 12 }}>
              Could not reach backend: {error} — check your FastAPI server is running on port 8000.
            </div>
          )}

          {showML ? (
            /* ── MODEL INTELLIGENCE VIEW ── */
            <>
              <div style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 13, color: 'var(--txm)', lineHeight: 1.8 }}>
                  Federated Learning trains across 3 clinic partitions independently, then aggregates into a global XGBoost dropout risk model.
                  The RL contextual bandit (Vowpal Wabbit) selects the optimal intervention per patient using the risk score as context.
                </div>
              </div>
              <MLInsights />
            </>
          ) : showInterventions ? (
            /* ── INTERVENTIONS VIEW ── */
            <Interventions />
          ) : (
            /* ── DASHBOARD VIEW ── */
            <>
              <KpiCards stats={stats} />
              <RiskChart trend={trend} stats={stats} />
              <PatientTable
                patients={visiblePatients}
                loading={loading}
                onSelect={setSelected}
              />
            </>
          )}
        </main>
      </div>

      {/* ── PATIENT DRAWER ── */}
      {selected && (
        <PatientDrawer
          patient={selected}
          onClose={() => setSelected(null)}
          onSchedule={() => openScheduleFor(selected)}
        />
      )}

      {/* ── SCHEDULE MODAL ── */}
      {scheduleFor && (
        <ScheduleModal
          patient={scheduleFor}
          onClose={() => setScheduleFor(null)}
          onSend={(msg) => {
            setScheduleFor(null)
            showToast(msg || 'Message sent via WhatsApp!')
          }}
        />
      )}

      {/* ── TOAST ── */}
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
