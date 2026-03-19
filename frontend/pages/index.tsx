import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function Dashboard() {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Hi! I\'m your health advocate. Ask me about your vitals, trends, or to book an appointment.' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [watching, setWatching] = useState(false)
  const [stepUpUrl, setStepUpUrl] = useState(null)
  const [fitLive, setFitLive] = useState<boolean | null>(null)
  const chatEndRef = useRef(null)
  const userId = 'demo-user-001'

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Poll Google Fit connection status
  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${API}/api/connection-status?user_id=${userId}`)
        if (res.ok) {
          const data = await res.json()
          setFitLive(!!data.google_fit_live)
        }
      } catch { /* backend not running yet */ }
    }
    check()
    const interval = setInterval(check, 15_000)
    return () => clearInterval(interval)
  }, [])

  const sendMessage = async () => {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: userMsg }])
    setLoading(true)

    try {
      const res = await fetch(`${API}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, message: userMsg })
      })
      const data = await res.json()

      if (data.response.status === 'step_up_required') {
        setStepUpUrl(data.response.challenge_url)
        setMessages(prev => [...prev, { role: 'assistant', text: data.response.response, stepUp: true }])
      } else {
        setMessages(prev => [...prev, { role: 'assistant', text: data.response.response || data.response }])
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', text: 'Error connecting to agent. Is the backend running?' }])
    }
    setLoading(false)
  }

  const toggleWatch = async () => {
    const endpoint = watching ? '/api/stop-watching' : '/api/start-watching'
    await fetch(`${API}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, threshold_bpm: 100 })
    })
    setWatching(!watching)
  }

  return (
    <div style={{ maxWidth: 700, margin: '0 auto', padding: '24px 16px', fontFamily: 'system-ui, sans-serif' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 500 }}>Health Advocate</h1>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#666' }}>Privacy-first AI health agent</p>
        </div>
        <button
          onClick={toggleWatch}
          style={{
            padding: '8px 16px',
            borderRadius: 8,
            border: `1px solid ${watching ? '#0F6E56' : '#ccc'}`,
            background: watching ? '#E1F5EE' : 'transparent',
            color: watching ? '#0F6E56' : '#555',
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: 500
          }}
        >
          {watching ? '● Watching' : '○ Start watching'}
        </button>
      </div>

      {/* Google Fit status banner */}
      {fitLive === false && (
        <div style={{
          padding: '10px 14px', marginBottom: 12,
          background: '#FEFCE8', border: '1px solid #FCD34D',
          borderRadius: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center'
        }}>
          <span style={{ fontSize: 13, color: '#78350F' }}>
            ⚠️ Using <strong>mock health data</strong> — connect Google Fit for real readings
          </span>
          <Link href="/settings" style={{
            padding: '5px 12px', background: '#F59E0B', color: '#fff',
            borderRadius: 6, fontSize: 12, textDecoration: 'none', fontWeight: 600
          }}>
            Connect →
          </Link>
        </div>
      )}
      {fitLive === true && (
        <div style={{
          padding: '8px 14px', marginBottom: 12,
          background: '#E1F5EE', border: '1px solid #5DCAA5',
          borderRadius: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center'
        }}>
          <span style={{ fontSize: 13, color: '#0F4F3E' }}>
            🟢 <strong>Google Fit live</strong> — reading real heart rate, steps & sleep
          </span>
          <Link href="/settings" style={{ fontSize: 12, color: '#0F6E56', textDecoration: 'none' }}>
            Manage →
          </Link>
        </div>
      )}

      {/* Step-up banner */}
      {stepUpUrl && (
        <div style={{
          padding: '12px 16px', marginBottom: 16,
          background: '#FAEEDA', border: '1px solid #EF9F27',
          borderRadius: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center'
        }}>
          <span style={{ fontSize: 13, color: '#633806' }}>Biometric verification required to continue</span>
          <a
            href={stepUpUrl}
            target="_blank"
            rel="noreferrer"
            style={{
              padding: '6px 14px', background: '#BA7517', color: '#fff',
              borderRadius: 6, fontSize: 13, textDecoration: 'none', fontWeight: 500
            }}
          >
            Verify identity ↗
          </a>
        </div>
      )}

      {/* Chat area */}
      <div style={{
        border: '0.5px solid #e0e0e0', borderRadius: 12,
        minHeight: 400, maxHeight: 480, overflowY: 'auto',
        padding: 16, marginBottom: 12, background: '#fafafa'
      }}>
        {messages.map((msg, i) => (
          <div key={i} style={{
            display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            marginBottom: 12
          }}>
            <div style={{
              maxWidth: '80%', padding: '10px 14px',
              borderRadius: msg.role === 'user' ? '12px 12px 4px 12px' : '12px 12px 12px 4px',
              background: msg.role === 'user' ? '#E6F1FB' : '#fff',
              border: msg.role === 'user' ? '0.5px solid #85B7EB' : '0.5px solid #e0e0e0',
              fontSize: 14, lineHeight: 1.5,
              color: msg.role === 'user' ? '#042C53' : '#222'
            }}>
              {msg.text}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', gap: 4, padding: '8px 0' }}>
            {[0,1,2].map(i => (
              <div key={i} style={{
                width: 8, height: 8, borderRadius: '50%', background: '#aaa',
                animation: `pulse 1s ease-in-out ${i * 0.2}s infinite`
              }}/>
            ))}
          </div>
        )}
        <div ref={chatEndRef}/>
      </div>

      {/* Input */}
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendMessage()}
          placeholder="Ask about your health, book an appointment..."
          style={{
            flex: 1, padding: '10px 14px', borderRadius: 8,
            border: '0.5px solid #ccc', fontSize: 14, outline: 'none'
          }}
        />
        <button
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          style={{
            padding: '10px 20px', borderRadius: 8,
            background: '#185FA5', color: '#fff', border: 'none',
            cursor: loading ? 'not-allowed' : 'pointer', fontSize: 14,
            opacity: loading ? 0.6 : 1
          }}
        >
          Send
        </button>
      </div>

      {/* Privacy note */}
      <p style={{ marginTop: 12, fontSize: 12, color: '#999', textAlign: 'center' }}>
        Raw health data is never stored. Only AI summaries are kept in your session.
      </p>

      <style>{`@keyframes pulse { 0%,100%{opacity:0.3} 50%{opacity:1} }`}</style>
    </div>
  )
}
