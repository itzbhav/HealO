import { useState } from 'react'

const FILTERS = ['All','High','Medium','Low']

export default function PatientTable({ patients, loading, onSelect }) {
  const [filter, setFilter] = useState('All')
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState('risk_score')
  const [sortDir, setSortDir] = useState(-1)

  // exposed for topbar search — parent passes search prop instead
  const filtered = patients
    .filter(p => filter === 'All' || p.risk_label === filter)
    .sort((a, b) => {
      let av = a[sortKey], bv = b[sortKey]
      if (typeof av === 'string') { av = av.toLowerCase(); bv = bv.toLowerCase() }
      return av < bv ? sortDir : av > bv ? -sortDir : 0
    })

  function toggleSort(key) {
    if (sortKey === key) setSortDir(d => -d)
    else { setSortKey(key); setSortDir(-1) }
  }

  const sortArrow = (key) => sortKey === key ? (sortDir === -1 ? ' ↓' : ' ↑') : ''

  return (
    <div className="table-card">
      <div className="table-head">
        <span className="table-title">Patient Risk Board</span>
        <div className="filter-row">
          {FILTERS.map(f => (
            <button key={f}
              className={`filter-btn ${filter === f ? 'active' : ''}`}
              onClick={() => setFilter(f)}>{f}</button>
          ))}
        </div>
      </div>
      <div className="table-wrap">
        {loading ? (
          Array.from({length:8}).map((_, i) => (
            <div key={i} className="skel-row">
              <div className="skeleton skel-av" />
              <div className="skel-lines">
                <div className="skeleton skel-line" style={{width:`${50+Math.random()*30}%`}} />
                <div className="skeleton skel-line" style={{width:`${30+Math.random()*20}%`}} />
              </div>
            </div>
          ))
        ) : filtered.length === 0 ? (
          <div className="empty">
            <div className="empty-icon">🔍</div>
            <div className="empty-text">No patients match this filter</div>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Patient</th>
                <th className="sortable" onClick={() => toggleSort('risk_label')}>Risk{sortArrow('risk_label')}</th>
                <th className="sortable" onClick={() => toggleSort('risk_score')}>Score{sortArrow('risk_score')}</th>
                <th>Action</th>
                <th>Doctor</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => {
                const pct  = Math.round(p.risk_score * 100)
                const fill = p.risk_label === 'High' ? 'var(--hi)' : p.risk_label === 'Medium' ? 'var(--med)' : 'var(--lo)'
                const act  = (p.action || '—').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
                return (
                  <tr key={p.id} onClick={() => onSelect(p)}>
                    <td>
                      <div className="pt-cell">
                        <div className="pt-av" style={{background: p.color}}>{p.ini}</div>
                        <div>
                          <div className="pt-name">{p.name}</div>
                          <div className="pt-dis">{p.disease}</div>
                        </div>
                      </div>
                    </td>
                    <td><span className={`risk-badge ${p.risk_label}`}>{p.risk_label}</span></td>
                    <td>
                      <div className="score-cell">
                        <div className="score-bar">
                          <div className="score-fill" style={{width:`${pct}%`, background:fill}} />
                        </div>
                        {pct}%
                      </div>
                    </td>
                    <td><span className="action-chip">{act}</span></td>
                    <td className="dr-col">{p.doctor}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
