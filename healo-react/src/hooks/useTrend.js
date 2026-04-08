import { useState, useEffect } from 'react'

export default function useTrend() {
  const [trend, setTrend] = useState(null)

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch('/api/dashboard/trend')
        if (res.ok) {
          setTrend(await res.json())
        }
      } catch {}
    }
    load()
  }, [])

  return trend
}
