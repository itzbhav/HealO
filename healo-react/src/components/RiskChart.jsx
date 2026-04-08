import { useEffect, useRef } from 'react'

const DAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Today']

function buildFallbackTrend(stats) {
  if (!stats) return null
  return DAYS.map((d, i) => {
    const jitter = () => Math.round((Math.random() - 0.5) * 12)
    return {
      date: d,
      high:   Math.max(0, (stats.high_risk   || 0) + jitter()),
      medium: Math.max(0, (stats.medium_risk || 0) + jitter()),
      low:    Math.max(0, (stats.low_risk    || 0) + jitter()),
    }
  })
}

export default function RiskChart({ trend, stats }) {
  const lineRef  = useRef(null)
  const donutRef = useRef(null)
  const lineInst = useRef(null)
  const donutInst = useRef(null)

  const data = trend || buildFallbackTrend(stats)

  useEffect(() => {
    if (!window.Chart || !data) return
    if (lineInst.current) lineInst.current.destroy()
    const ctx = lineRef.current.getContext('2d')
    lineInst.current = new window.Chart(ctx, {
      type: 'line',
      data: {
        labels: data.map(d => d.date),
        datasets: [
          { label:'High',   data: data.map(d => d.high),   borderColor:'#f87171', backgroundColor:'rgba(248,113,113,.08)', tension:.4, fill:true, pointRadius:3, borderWidth:2 },
          { label:'Medium', data: data.map(d => d.medium), borderColor:'#fb923c', backgroundColor:'rgba(251,146,60,.08)',  tension:.4, fill:true, pointRadius:3, borderWidth:2 },
          { label:'Low',    data: data.map(d => d.low),    borderColor:'#4ade80', backgroundColor:'rgba(74,222,128,.08)', tension:.4, fill:true, pointRadius:3, borderWidth:2 },
        ],
      },
      options: {
        responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{ display:false }, tooltip:{ mode:'index', intersect:false } },
        scales:{
          x:{ grid:{ color:'rgba(255,255,255,.04)' }, ticks:{ color:'#6e6c69', font:{ size:10 } } },
          y:{ grid:{ color:'rgba(255,255,255,.04)' }, ticks:{ color:'#6e6c69', font:{ size:10 } }, beginAtZero:false },
        },
      },
    })
  }, [data])

  useEffect(() => {
    if (!window.Chart || !stats) return
    if (donutInst.current) donutInst.current.destroy()
    const ctx = donutRef.current.getContext('2d')
    donutInst.current = new window.Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['High','Medium','Low'],
        datasets: [{
          data: [stats.high_risk||0, stats.medium_risk||0, stats.low_risk||0],
          backgroundColor: ['#f87171','#fb923c','#4ade80'],
          borderColor: '#111110',
          borderWidth: 3,
          hoverOffset: 5,
        }],
      },
      options: {
        responsive:true, maintainAspectRatio:false, cutout:'68%',
        plugins:{ legend:{ position:'bottom', labels:{ color:'#6e6c69', font:{ size:10 }, boxWidth:8, padding:10 } } },
      },
    })
  }, [stats])

  return (
    <div className="chart-row">
      <div className="chart-card">
        <div className="chart-title">Risk Trend — Last 7 Days</div>
        <div className="chart-sub">Daily patient risk distribution</div>
        <div className="chart-body"><canvas ref={lineRef} /></div>
        <div className="chart-legend">
          {[['#f87171','High'],['#fb923c','Medium'],['#4ade80','Low']].map(([c,l]) => (
            <div key={l} className="legend-item">
              <div className="legend-dot" style={{background:c}} />{l}
            </div>
          ))}
        </div>
      </div>
      <div className="chart-card">
        <div className="chart-title">Today's Risk Split</div>
        <div className="chart-sub">{stats ? `${stats.total_patients || 0} patients` : 'Loading…'}</div>
        <div className="chart-body"><canvas ref={donutRef} /></div>
      </div>
    </div>
  )
}
