import { useEffect, useRef } from 'react'

const CARDS = [
  { key:'total_patients', label:'Total Patients', cls:'kpi-total', icon:'👥', sub:'Active in system' },
  { key:'high_risk',      label:'High Risk',      cls:'kpi-high',  icon:'⚠️', sub:'Needs escalation' },
  { key:'medium_risk',    label:'Medium Risk',    cls:'kpi-med',   icon:'👁', sub:'Monitor closely' },
  { key:'low_risk',       label:'Low Risk',       cls:'kpi-low',   icon:'✅', sub:'Adherent patients' },
]

function AnimatedNum({ target }) {
  const ref = useRef(null)
  useEffect(() => {
    if (target == null) return
    const el = ref.current
    const dur = 800
    const start = performance.now()
    const from = 0
    function step(now) {
      const p = Math.min((now - start) / dur, 1)
      const ease = 1 - Math.pow(1 - p, 3)
      el.textContent = Math.round(from + (target - from) * ease).toLocaleString()
      if (p < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }, [target])
  return <span ref={ref}>—</span>
}

export default function KpiCards({ stats }) {
  return (
    <div className="kpi-grid">
      {CARDS.map(c => (
        <div key={c.key} className={`kpi-card ${c.cls}`}>
          <div className="kpi-top">
            <span className="kpi-label">{c.label}</span>
            <div className="kpi-ico">{c.icon}</div>
          </div>
          <div className="kpi-val">
            {stats ? <AnimatedNum target={stats[c.key] ?? 0} /> : '—'}
          </div>
          <div className="kpi-sub">{c.sub}</div>
        </div>
      ))}
    </div>
  )
}
