import { useState, useEffect } from 'react'

function Bar({ value, max, color }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        flex: 1, height: 8, background: 'rgba(255,255,255,0.06)',
        borderRadius: 99, overflow: 'hidden',
      }}>
        <div style={{
          width: `${pct}%`, height: '100%',
          background: color, borderRadius: 99,
          transition: 'width 0.6s cubic-bezier(.16,1,.3,1)',
        }} />
      </div>
      <span style={{ fontSize: 11, color: 'var(--txm)', minWidth: 36, textAlign: 'right' }}>
        {value}
      </span>
    </div>
  )
}

function AucBar({ local, federated }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--txm)', marginBottom: 2 }}>
        <span>Local model AUC</span>
        <span style={{ color: 'var(--med)' }}>{(local * 100).toFixed(1)}%</span>
      </div>
      <div style={{ height: 7, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ width: `${local * 100}%`, height: '100%', background: 'var(--med)', borderRadius: 99, transition: 'width .7s' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--txm)', marginTop: 4, marginBottom: 2 }}>
        <span>Federated AUC</span>
        <span style={{ color: 'var(--lo)' }}>{(federated * 100).toFixed(1)}%</span>
      </div>
      <div style={{ height: 7, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ width: `${federated * 100}%`, height: '100%', background: 'var(--lo)', borderRadius: 99, transition: 'width .7s' }} />
      </div>
    </div>
  )
}

const ACTION_COLORS = {
  morning_reminder:   '#38bdf8',
  evening_reminder:   '#a78bfa',
  motivational_message: '#4ade80',
  escalate_to_doctor: '#f87171',
  do_nothing:         '#6e6c69',
}

const ACTION_LABELS = {
  morning_reminder:     'Morning Reminder',
  evening_reminder:     'Evening Reminder',
  motivational_message: 'Motivational Nudge',
  escalate_to_doctor:   'Escalate to Doctor',
  do_nothing:           'Do Nothing',
}

export default function MLInsights() {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/ml-insights')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d && !d.error) setData(d) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const totalActions = data?.action_distribution?.reduce((s, a) => s + a.count, 0) || 1

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 14, margin: '0 0 14px' }}>

      {/* ── FL Clinic Panel ── */}
      <div className="chart-card" style={{ gridColumn: '1' }}>
        <div className="chart-title">Federated Learning — 3 Clinics</div>
        <div className="chart-sub">
          Local vs federated model AUC &nbsp;·&nbsp;
          Global AUC: <span style={{ color: 'var(--lo)', fontWeight: 600 }}>
            {data ? `${(data.global_auc * 100).toFixed(1)}%` : '—'}
          </span>
        </div>

        {loading ? (
          <div style={{ padding: '20px 0', color: 'var(--txm)', fontSize: 12 }}>Loading…</div>
        ) : data ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 14 }}>
            {data.clinic_results.map(c => (
              <div key={c.clinic}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 6 }}>
                  <span style={{ color: 'var(--tx)', fontWeight: 500 }}>{c.clinic}</span>
                  <span style={{ color: 'var(--txm)' }}>{c.patients} patients</span>
                </div>
                <AucBar local={c.local_auc} federated={c.federated_auc} />
                {c.federated_auc > c.local_auc && (
                  <div style={{ fontSize: 10, color: 'var(--lo)', marginTop: 4 }}>
                    +{((c.federated_auc - c.local_auc) * 100).toFixed(1)}% gain from federation
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: 'var(--txm)', fontSize: 12, marginTop: 12 }}>No data available</div>
        )}
      </div>

      {/* ── RL Action Distribution ── */}
      <div className="chart-card" style={{ gridColumn: '2' }}>
        <div className="chart-title">RL Agent — Action Distribution</div>
        <div className="chart-sub">Today's intervention decisions across all patients</div>

        {loading ? (
          <div style={{ padding: '20px 0', color: 'var(--txm)', fontSize: 12 }}>Loading…</div>
        ) : data ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 14 }}>
            {data.action_distribution.map(a => {
              const pct = Math.round((a.count / totalActions) * 100)
              const color = ACTION_COLORS[a.action] || '#6e6c69'
              const label = ACTION_LABELS[a.action] || a.action
              return (
                <div key={a.action}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                    <span style={{ color: 'var(--tx)' }}>{label}</span>
                    <span style={{ color: 'var(--txm)' }}>{pct}%</span>
                  </div>
                  <Bar value={a.count} max={totalActions} color={color} />
                </div>
              )
            })}
            <div style={{ fontSize: 10, color: 'var(--txm)', marginTop: 4, borderTop: '1px solid var(--bord)', paddingTop: 8 }}>
              Contextual bandit (Vowpal Wabbit) · ε-greedy exploration
            </div>
          </div>
        ) : (
          <div style={{ color: 'var(--txm)', fontSize: 12, marginTop: 12 }}>No data available</div>
        )}
      </div>

      {/* ── Feature Importance ── */}
      <div className="chart-card" style={{ gridColumn: '3' }}>
        <div className="chart-title">XGBoost — Feature Importance</div>
        <div className="chart-sub">Dropout risk model · Top predictors</div>

        {loading ? (
          <div style={{ padding: '20px 0', color: 'var(--txm)', fontSize: 12 }}>Loading…</div>
        ) : data ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 14 }}>
            {data.feature_importance.length > 0 ? (
              data.feature_importance.map(f => {
                const pct = Math.round(f.importance * 100)
                const hue = Math.round(180 - f.importance * 120)
                return (
                  <div key={f.feature}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                      <span style={{ color: 'var(--tx)', textTransform: 'capitalize' }}>{f.feature}</span>
                      <span style={{ color: 'var(--txm)' }}>{pct}%</span>
                    </div>
                    <Bar value={pct} max={100} color={`hsl(${hue},70%,60%)`} />
                  </div>
                )
              })
            ) : (
              <div style={{ fontSize: 11, color: 'var(--txm)' }}>
                Model uses all features equally — retrain with more varied data for importance spread.
              </div>
            )}
            <div style={{ fontSize: 10, color: 'var(--txm)', marginTop: 4, borderTop: '1px solid var(--bord)', paddingTop: 8 }}>
              Federated XGBoost · 3-clinic aggregation · AUC {data ? (data.global_auc * 100).toFixed(1) : '—'}%
            </div>
          </div>
        ) : (
          <div style={{ color: 'var(--txm)', fontSize: 12, marginTop: 12 }}>No data available</div>
        )}
      </div>

    </div>
  )
}
