import { useState, useEffect, useCallback } from 'react'

function CallButton({ patientId }) {
  const [status, setStatus] = useState('idle')

  const handleCall = useCallback(async () => {
    setStatus('calling')
    try {
      const res  = await fetch(`/webhook/initiate-call/${patientId}`, { method: 'POST' })
      const data = await res.json()
      setStatus(data.error ? 'error' : 'done')
      setTimeout(() => setStatus('idle'), 5000)
    } catch {
      setStatus('error')
      setTimeout(() => setStatus('idle'), 3000)
    }
  }, [patientId])

  const cfg = {
    idle:    { label: '📞 AI Call',    cls: 'btn-secondary' },
    calling: { label: '📞 Dialling…', cls: 'btn-secondary' },
    done:    { label: 'Called',        cls: 'btn-secondary' },
    error:   { label: 'Call Failed',   cls: 'btn-danger'    },
  }[status]

  return (
    <button className={cfg.cls} onClick={handleCall} disabled={status !== 'idle'}>
      {cfg.label}
    </button>
  )
}

export default function PatientDrawer({ patient: p, onClose, onSchedule }) {
  const pct  = Math.round(p.risk_score * 100)
  const rc   = p.risk_label === 'High' ? 'var(--hi)' : p.risk_label === 'Medium' ? 'var(--med)' : 'var(--lo)'

  const [explanation, setExplanation] = useState(null)
  const [loadingExp,  setLoadingExp]  = useState(false)

  useEffect(() => {
    if (!p.id) return
    setExplanation(null)
    setLoadingExp(true)
    fetch(`/api/dashboard/patient/${p.id}/explanation`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setExplanation(d.explanation) })
      .catch(() => {})
      .finally(() => setLoadingExp(false))
  }, [p.id])

  const replyPct  = Math.round((p.reply_rate    || 0) * 100)
  const adherePct = Math.round((p.med_adherence || 0) * 100)

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer">
        <div className="drawer-inner">
          {/* Header */}
          <div className="dh">
            <div className="d-av" style={{background:`linear-gradient(135deg,${p.color},#10b981)`}}>{p.ini}</div>
            <div>
              <div className="d-name">{p.name}</div>
              <div className="d-sub">{p.disease} · {p.doctor}</div>
            </div>
            <button className="d-close" onClick={onClose}>✕</button>
          </div>

          {/* Stats grid */}
          <div className="d-grid">
            {[
              ['Risk Score',      `${pct}%`,                      rc],
              ['Risk Level',      p.risk_label,                   rc],
              ['Reply Rate',      `${replyPct}%`,                 replyPct > 60 ? 'var(--ok)' : 'var(--hi)'],
              ['Med Adherence',   `${adherePct}%`,                adherePct > 60 ? 'var(--ok)' : 'var(--hi)'],
              ['Days Silent',     `${p.days_silent ?? 0}d`,       (p.days_silent || 0) >= 3 ? 'var(--hi)' : null],
              ['Streak (30d)',    `${p.streak ?? 0} days`,        null],
              ['Disease',         p.disease,                      null],
              ['Action Today',    (p.action || '—').replace(/_/g,' '), null],
            ].map(([label, val, color]) => (
              <div key={label} className="d-stat">
                <div className="d-stat-label">{label}</div>
                <div className="d-stat-val" style={color ? {color} : {}}>{val}</div>
              </div>
            ))}
          </div>

          {/* AI Explanation */}
          <div style={{marginTop: 16}}>
            <div className="d-section-title" style={{display:'flex', alignItems:'center', gap:6}}>
              AI Risk Explanation
              {loadingExp && <span style={{fontSize:10, color:'var(--muted)', fontWeight:400}}>generating…</span>}
            </div>
            <div style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 8,
              padding: '10px 12px',
              fontSize: 12,
              lineHeight: 1.6,
              color: loadingExp ? 'var(--muted)' : 'var(--fg)',
              minHeight: 48,
            }}>
              {loadingExp
                ? 'Analysing patient data…'
                : explanation || 'No explanation available yet.'}
            </div>
          </div>

          {/* Activity timeline */}
          <div style={{marginTop: 16}}>
            <div className="d-section-title">Today's Pipeline</div>
            <div className="d-tl">
              {[
                ['Risk score computed',        p.risk_label ? `${pct}% — ${p.risk_label}` : '—'],
                ['RL agent action selected',   (p.action || '—').replace(/_/g,' ')],
                ['Message status',             p.message_sent ? 'Sent via WhatsApp' : 'No message sent'],
                ['Last seen',                  p.days_silent === 0 ? 'Today' : `${p.days_silent}d ago`],
              ].map(([evt, detail], i) => (
                <div key={i} className="d-tl-item">
                  <div className="d-tl-dot" />
                  <div>
                    <div className="d-tl-text">{evt}</div>
                    <div className="d-tl-time">{detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="d-footer">
          <CallButton patientId={p.id} />
          <button className="btn-secondary" onClick={onClose}>Close</button>
          <button className="btn-primary" onClick={onSchedule}>📤 Message</button>
        </div>
      </div>
    </>
  )
}
