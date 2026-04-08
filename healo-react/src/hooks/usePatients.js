import { useState, useEffect } from 'react'

const COLORS = [
  '#2dd4bf','#10b981','#fb923c','#a78bfa',
  '#38bdf8','#f472b6','#facc15','#4ade80',
]

function ini(name = '') {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
}

export default function usePatients() {
  const [patients, setPatients] = useState([])
  const [stats, setStats]       = useState(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)

  useEffect(() => {
    async function load() {
      try {
        const [pRes, sRes] = await Promise.all([
          fetch('/api/dashboard'),
          fetch('/api/dashboard/stats'),
        ])
        if (!pRes.ok) throw new Error(`patients ${pRes.status}`)
        const raw = await pRes.json()

        const mapped = Array.isArray(raw)
          ? raw.map((p, i) => ({
              ...p,
              id:         p.id ?? i,
              name:       p.full_name || p.name || `Patient ${i + 1}`,
              disease:    p.disease_type || p.disease || '—',
              doctor:     p.assigned_doctor || p.doctor_name || p.doctor || '—',
              risk_score: parseFloat(p.risk_score ?? 0),
              risk_label: p.risk_label || 'Low',
              action:     p.action_taken || p.action || '—',
              ini:        ini(p.full_name || p.name || ''),
              color:      COLORS[i % COLORS.length],
            }))
          : []

        setPatients(mapped)
        if (sRes.ok) setStats(await sRes.json())
        else {
          // compute from data
          const h = mapped.filter(p => p.risk_label === 'High').length
          const m = mapped.filter(p => p.risk_label === 'Medium').length
          const l = mapped.filter(p => p.risk_label === 'Low').length
          setStats({ total_patients: mapped.length, high_risk: h, medium_risk: m, low_risk: l })
        }
      } catch (e) {
        setError(e.message)
      }
      setLoading(false)
    }
    load()
  }, [])

  return { patients, stats, loading, error }
}
