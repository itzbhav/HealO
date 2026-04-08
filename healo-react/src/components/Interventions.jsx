import { useState, useEffect } from 'react'

function CallButton({ patientId, patientName }) {
  const [status, setStatus] = useState('idle')  // idle | calling | done | error
  const [errMsg, setErrMsg] = useState('')

  async function handleCall() {
    setStatus('calling')
    setErrMsg('')
    try {
      const res  = await fetch(`/webhook/initiate-call/${patientId}`, { method: 'POST' })
      const data = await res.json()
      if (data.error) {
        setErrMsg(data.error)
        setStatus('error')
        setTimeout(() => setStatus('idle'), 6000)
        return
      }
      setStatus('done')
      setTimeout(() => setStatus('idle'), 5000)
    } catch {
      setStatus('error')
      setErrMsg('Network error')
      setTimeout(() => setStatus('idle'), 3000)
    }
  }

  const label = { idle: 'AI Call', calling: 'Dialling…', done: 'Called', error: 'Failed' }[status]
  const bg    = { idle: 'var(--prihlt)', calling: 'var(--medbg)', done: 'var(--lobg)', error: 'var(--hibg)' }[status]
  const color = { idle: 'var(--pri)',    calling: 'var(--med)',   done: 'var(--lo)',   error: 'var(--hi)'   }[status]

  return (
    <div style={{ flexShrink: 0, textAlign: 'right' }}>
      <button
        onClick={handleCall}
        disabled={status === 'calling' || status === 'done'}
        style={{
          background: bg, color, border: 'none', borderRadius: 99,
          fontSize: 12, fontWeight: 600, padding: '5px 14px',
          cursor: status === 'idle' ? 'pointer' : 'default',
          transition: 'all 0.2s', display: 'block',
        }}>
        {status === 'done' ? '✓ ' : '📞 '}{label}
      </button>
      {errMsg && (
        <div style={{ fontSize: 10, color: 'var(--hi)', marginTop: 3, maxWidth: 160 }}>
          {errMsg}
        </div>
      )}
    </div>
  )
}

export default function Interventions() {
  const [patients, setPatients] = useState([])
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    fetch('/api/dashboard')
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        // Only show patients flagged for escalation or high risk with no recent reply
        // Priority score: weight risk + silence heavily
        // Only show patients who are BOTH escalated AND have been silent 3+ days
        // OR genuinely high risk (>85%) with low adherence (<30%)
        const flagged = data
          .filter(p =>
            (p.action_taken === 'escalate_to_doctor' && p.days_silent >= 3) ||
            (p.risk_score > 0.85 && (p.med_adherence || 0) < 0.3 && p.days_silent >= 2)
          )
          .sort((a, b) => b.risk_score - a.risk_score || b.days_silent - a.days_silent)
          .slice(0, 30)   // cap at 30 most critical
        setPatients(flagged)
      })
      .catch(() => setPatients([]))
      .finally(() => setLoading(false))
  }, [])

  const COLORS = ['#f87171','#fb923c','#a78bfa','#38bdf8','#4ade80']
  function ini(name = '') { return name.split(' ').map(w => w[0]).join('').slice(0,2).toUpperCase() }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 13, color: 'var(--txm)', lineHeight: 1.8 }}>
          High-priority patients: RL agent escalated AND silent for 3+ days, or risk above 85% with adherence below 30%.
          Sorted by urgency score. Use AI Call to reach them directly.
        </div>
      </div>

      {loading ? (
        <div style={{ color: 'var(--txm)', fontSize: 14, padding: 20 }}>Loading interventions…</div>
      ) : patients.length === 0 ? (
        <div className="chart-card" style={{ textAlign: 'center', padding: 40 }}>
          <div style={{ fontSize: 32, marginBottom: 10 }}>✅</div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>No active interventions today</div>
          <div style={{ fontSize: 13, color: 'var(--txm)', marginTop: 4 }}>All patients are within acceptable adherence thresholds.</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ fontSize: 13, color: 'var(--txm)', marginBottom: 4 }}>
            {patients.length} patient{patients.length !== 1 ? 's' : ''} require attention
          </div>
          {patients.map((p, i) => {
            const pct = Math.round(p.risk_score * 100)
            const adherePct = Math.round((p.med_adherence || 0) * 100)
            const color = COLORS[i % COLORS.length]
            return (
              <div key={p.id} className="chart-card" style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 18px' }}>
                {/* Avatar */}
                <div style={{
                  width: 42, height: 42, borderRadius: '50%', flexShrink: 0,
                  background: `linear-gradient(135deg,${color},#10b981)`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13, fontWeight: 700, color: '#fff',
                }}>
                  {ini(p.full_name)}
                </div>

                {/* Name + disease */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>{p.full_name}</div>
                  <div style={{ fontSize: 13, color: 'var(--txm)' }}>{p.disease} · {p.assigned_doctor}</div>
                </div>

                {/* Stats */}
                <div style={{ display: 'flex', gap: 24, flexShrink: 0 }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 11, color: 'var(--txm)', textTransform: 'uppercase', letterSpacing: '.06em' }}>Risk</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--hi)' }}>{pct}%</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 11, color: 'var(--txm)', textTransform: 'uppercase', letterSpacing: '.06em' }}>Silent</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: p.days_silent >= 3 ? 'var(--hi)' : 'var(--med)' }}>
                      {p.days_silent}d
                    </div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 11, color: 'var(--txm)', textTransform: 'uppercase', letterSpacing: '.06em' }}>Adherence</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: adherePct > 50 ? 'var(--lo)' : 'var(--hi)' }}>
                      {adherePct}%
                    </div>
                  </div>
                </div>

                {/* Action badge */}
                <div style={{
                  background: 'var(--hibg)', color: 'var(--hi)',
                  fontSize: 12, fontWeight: 600, padding: '4px 12px',
                  borderRadius: 99, flexShrink: 0, whiteSpace: 'nowrap',
                }}>
                  {(p.action_taken || '').replace(/_/g, ' ')}
                </div>

                {/* AI Call button */}
                <CallButton patientId={p.id} patientName={p.full_name} />
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
