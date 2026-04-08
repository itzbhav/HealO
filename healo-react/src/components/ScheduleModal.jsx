import { useState } from 'react'

const TYPES = {
  rem: { label: 'Medication Reminder',  preview: 'HEALo: Good morning! Time for your Diabetes medication. Reply YES once taken, or NO if missed. 💊' },
  mot: { label: 'Motivational Nudge',   preview: 'HEALo: Every dose brings you closer to better health. Keep up the streak! Reply YES if taken today. 💪' },
  fu:  { label: 'Follow-up Check',      preview: 'HEALo: Hi! How are you feeling today? Any symptoms to report? Your care team is here for you. 👋' },
  apt: { label: 'Appointment Reminder', preview: 'HEALo: You have an upcoming appointment with Dr. Priya. Reply CONFIRM to confirm or CANCEL to reschedule. 📅' },
}

export default function ScheduleModal({ patient, onClose, onSend }) {
  const [type,    setType]    = useState('rem')
  const [sending, setSending] = useState(false)
  const [result,  setResult]  = useState(null)   // 'ok' | 'fail'

  async function handleSend() {
    setSending(true)
    setResult(null)
    try {
      const res = await fetch('/api/schedule-message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: patient?.id,
          message:    TYPES[type].preview,
        }),
      })
      const data = await res.json()
      if (data.status === 'sent') {
        setResult('ok')
        setTimeout(() => {
          onSend('Message sent via WhatsApp!')
        }, 1200)
      } else {
        setResult('fail')
      }
    } catch {
      setResult('fail')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="m-head">
          <div>
            <h3>Send WhatsApp Message</h3>
            <p>Send to {patient?.name || 'patient'} via HEALo · Twilio</p>
          </div>
          <button className="m-close" onClick={onClose}>✕</button>
        </div>

        <div className="m-body">
          <div className="fg">
            <label>Patient</label>
            <div className="finp" style={{ cursor: 'default', opacity: .7 }}>
              {patient?.name || '—'} · {patient?.disease || '—'}
            </div>
          </div>

          <div className="fg">
            <label>Message Type</label>
            <select className="fsel" value={type} onChange={e => { setType(e.target.value); setResult(null) }}>
              {Object.entries(TYPES).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
          </div>

          <div className="fg">
            <label>Preview</label>
            <div className="msg-prev">{TYPES[type].preview}</div>
          </div>

          {result === 'ok' && (
            <div style={{ background: 'var(--lobg)', color: 'var(--lo)', padding: '8px 12px', borderRadius: 6, fontSize: 12 }}>
              Sent! Check {patient?.name}'s WhatsApp.
            </div>
          )}
          {result === 'fail' && (
            <div style={{ background: 'var(--hibg)', color: 'var(--hi)', padding: '8px 12px', borderRadius: 6, fontSize: 12 }}>
              Send failed — check Twilio credentials and sandbox join status.
            </div>
          )}
        </div>

        <div className="m-foot">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={handleSend} disabled={sending || result === 'ok'}>
            {sending ? 'Sending…' : result === 'ok' ? 'Sent!' : '📤 Send via WhatsApp'}
          </button>
        </div>
      </div>
    </div>
  )
}
