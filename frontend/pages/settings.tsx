import { useState, useEffect, useCallback } from 'react'
import Head from 'next/head'
import Link from 'next/link'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const USER_ID = 'demo-user-001'

interface StatusState {
  google_fit: 'unknown' | 'connected_live' | 'disconnected'
  fhir: 'unknown' | 'connected_live' | 'disconnected'
}

const SERVICE_META = {
  google_fit: {
    name: 'Google Fit',
    desc: 'Heart rate, steps & sleep — live from your device',
    scope: 'Read-only',
    icon: '💓',
    color: '#0F6E56',
    bg: '#E1F5EE',
    border: '#5DCAA5',
  },
  fhir: {
    name: 'Hospital Portal',
    desc: 'Medical records and appointments',
    scope: 'Read + Write (step-up auth)',
    icon: '🏥',
    color: '#185FA5',
    bg: '#E6F1FB',
    border: '#85B7EB',
  },
}

export default function Settings() {
  const [status, setStatus] = useState<StatusState>({ google_fit: 'unknown', fhir: 'unknown' })
  const [loading, setLoading] = useState(true)
  const [disconnecting, setDisconnecting] = useState<string | null>(null)
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null)

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3500)
  }

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/connection-status?user_id=${USER_ID}`)
      if (!res.ok) throw new Error('Backend unreachable')
      const data = await res.json()

      const next: StatusState = { google_fit: 'disconnected', fhir: 'disconnected' }
      if (data.google_fit_live) next.google_fit = 'connected_live'
      if ((data.connected_services || []).includes('fhir')) next.fhir = 'connected_live'
      setStatus(next)
    } catch {
      setStatus({ google_fit: 'disconnected', fhir: 'disconnected' })
    } finally {
      setLoading(false)
    }
  }, [])

  // On mount: check if we just came back from OAuth
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('connected') === 'google_fit') {
      showToast('✅ Google Fit connected! Live data is now active.')
      window.history.replaceState({}, '', '/settings')
    }
    fetchStatus()
    // Poll every 10s so status stays fresh after OAuth redirect
    const interval = setInterval(fetchStatus, 10_000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  const connectGoogleFit = () => {
    // Redirect to backend which starts real Google OAuth flow
    window.location.href = `${API}/api/auth/google?user_id=${USER_ID}`
  }

  const disconnect = async (serviceId: string) => {
    setDisconnecting(serviceId)
    try {
      const res = await fetch(`${API}/api/revoke/${serviceId}?user_id=${USER_ID}`, {
        method: 'DELETE',
      })
      if (!res.ok) throw new Error('Failed')
      setStatus(prev => ({ ...prev, [serviceId]: 'disconnected' }))
      showToast(`${SERVICE_META[serviceId as keyof typeof SERVICE_META].name} disconnected.`, false)
    } catch {
      showToast('Could not disconnect. Try again.', false)
    } finally {
      setDisconnecting(null)
    }
  }

  const isConnected = (id: string) => status[id as keyof StatusState] === 'connected_live'

  return (
    <>
      <Head>
        <title>Connected Services — Health Advocate</title>
        <meta name="description" content="Manage your connected health data services" />
      </Head>

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', top: 20, left: '50%', transform: 'translateX(-50%)',
          padding: '12px 20px', borderRadius: 10, zIndex: 9999,
          background: toast.ok ? '#E1F5EE' : '#FCEBEB',
          border: `1px solid ${toast.ok ? '#5DCAA5' : '#F09595'}`,
          color: toast.ok ? '#0F6E56' : '#791F1F',
          fontSize: 14, fontWeight: 500, boxShadow: '0 4px 16px rgba(0,0,0,0.1)',
          animation: 'fadeIn 0.2s ease',
        }}>
          {toast.msg}
        </div>
      )}

      <div style={{
        maxWidth: 620, margin: '0 auto', padding: '32px 16px',
        fontFamily: "'Inter', system-ui, sans-serif",
      }}>
        {/* Back nav */}
        <Link href="/" style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          fontSize: 13, color: '#666', textDecoration: 'none', marginBottom: 24,
        }}>
          ← Back to Dashboard
        </Link>

        <h1 style={{ fontSize: 24, fontWeight: 600, margin: '0 0 4px' }}>
          Connected Services
        </h1>
        <p style={{ fontSize: 14, color: '#666', marginBottom: 28, margin: '4px 0 28px' }}>
          Control which services your health agent can access. Disconnect anytime.
        </p>

        {/* Service cards */}
        {(Object.keys(SERVICE_META) as (keyof typeof SERVICE_META)[]).map(id => {
          const svc = SERVICE_META[id]
          const connected = isConnected(id)
          const busy = disconnecting === id
          const unknown = status[id] === 'unknown' || loading

          return (
            <div key={id} style={{
              border: `1px solid ${connected ? svc.border : '#e4e4e4'}`,
              borderRadius: 14, padding: '20px 22px', marginBottom: 14,
              background: connected ? svc.bg : '#fff',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              transition: 'all 0.3s ease',
              boxShadow: connected ? `0 2px 12px ${svc.border}33` : '0 1px 4px rgba(0,0,0,0.05)',
            }}>
              <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                {/* Icon */}
                <div style={{
                  fontSize: 26, width: 48, height: 48, borderRadius: 12,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: connected ? `${svc.color}15` : '#f5f5f5',
                  flexShrink: 0,
                }}>
                  {svc.icon}
                </div>

                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 15, fontWeight: 600, color: '#111' }}>
                      {svc.name}
                    </span>
                    {connected && (
                      <span style={{
                        fontSize: 11, fontWeight: 600, padding: '2px 8px',
                        borderRadius: 20, background: svc.color, color: '#fff',
                        letterSpacing: '0.02em',
                      }}>
                        ● LIVE
                      </span>
                    )}
                    {unknown && (
                      <span style={{ fontSize: 11, color: '#aaa' }}>checking…</span>
                    )}
                  </div>
                  <div style={{ fontSize: 13, color: '#555', marginTop: 3 }}>
                    {svc.desc}
                  </div>
                  <span style={{
                    display: 'inline-block', marginTop: 6,
                    padding: '2px 10px', borderRadius: 20, fontSize: 11,
                    background: '#F0F0F0', color: '#555', border: '0.5px solid #ddd',
                  }}>
                    {svc.scope}
                  </span>
                </div>
              </div>

              {/* Action button */}
              <div style={{ flexShrink: 0, marginLeft: 12 }}>
                {connected ? (
                  <button
                    id={`disconnect-${id}`}
                    onClick={() => disconnect(id)}
                    disabled={busy}
                    style={{
                      padding: '8px 16px', borderRadius: 9, fontSize: 13,
                      border: '1px solid #F09595', background: busy ? '#f5f5f5' : '#FCEBEB',
                      color: '#791F1F', cursor: busy ? 'not-allowed' : 'pointer',
                      fontWeight: 500, transition: 'all 0.2s',
                      opacity: busy ? 0.6 : 1,
                    }}
                  >
                    {busy ? 'Removing…' : 'Disconnect'}
                  </button>
                ) : (
                  <button
                    id={`connect-${id}`}
                    onClick={id === 'google_fit' ? connectGoogleFit : undefined}
                    disabled={unknown}
                    style={{
                      padding: '8px 16px', borderRadius: 9, fontSize: 13,
                      border: `1px solid ${svc.border}`,
                      background: unknown ? '#f5f5f5' : svc.bg,
                      color: unknown ? '#aaa' : svc.color,
                      cursor: unknown ? 'default' : 'pointer',
                      fontWeight: 600, transition: 'all 0.2s',
                    }}
                  >
                    {unknown ? '…' : 'Connect →'}
                  </button>
                )}
              </div>
            </div>
          )
        })}

        {/* What happens when connected */}
        {isConnected('google_fit') && (
          <div style={{
            marginTop: 8, padding: '16px 18px',
            background: '#F0FDF8', borderRadius: 12,
            border: '1px solid #AADFC8', fontSize: 13, color: '#0F4F3E',
            lineHeight: 1.6,
          }}>
            <strong>🟢 Google Fit is live.</strong> Your health agent is now reading real heart rate,
            step count, and sleep data from Google Fit. Ask it anything — it will use your actual data.
          </div>
        )}

        {/* Privacy note */}
        <div style={{
          marginTop: 20, padding: '14px 16px',
          background: '#F8F7F2', borderRadius: 10,
          fontSize: 13, color: '#555', lineHeight: 1.6,
        }}>
          <strong>Your privacy:</strong> Raw health data is never stored outside your
          Auth0-protected session. The AI only sees summaries it generates itself.
          Write actions always require biometric re-verification.
        </div>
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
        @keyframes fadeIn { from { opacity: 0; transform: translateX(-50%) translateY(-8px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
      `}</style>
    </>
  )
}
