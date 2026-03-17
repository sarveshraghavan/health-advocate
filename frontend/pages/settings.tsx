import { useState } from 'react'

const services = [
  { id: 'google_fit', name: 'Google Fit', desc: 'Heart rate, steps, sleep data', scope: 'Read-only' },
  { id: 'fhir', name: 'Hospital Portal', desc: 'Medical records, appointments', scope: 'Read + Write (step-up)' },
]

export default function Settings() {
  const [connected, setConnected] = useState({ google_fit: false, fhir: false })
  const userId = 'demo-user-001'
  const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  const disconnect = async (serviceId: string) => {
    await fetch(`${API}/api/revoke/${serviceId}?user_id=${userId}`, { method: 'DELETE' })
    setConnected(prev => ({ ...prev, [serviceId]: false }))
  }

  const connect = (serviceId: string) => {
    // Uses NEXT_PUBLIC_AUTH0_DOMAIN to redirect to the real Auth0 OAuth flow
    const tenant = process.env.NEXT_PUBLIC_AUTH0_DOMAIN || "dev-64lgvyfco02u52k1.us.auth0.com";
    window.open(`https://${tenant}/authorize?response_type=code&client_id=${process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID || 'Xry0va6GdiImIMdRZU7f7a0XjNWyllXk'}&redirect_uri=${API}/api/auth/callback&connection=${serviceId}&scope=openid%20profile%20offline_access`, '_blank');
    
    // Optimistically show connected after the popup opens
    setTimeout(() => setConnected(prev => ({ ...prev, [serviceId]: true })), 2000)
  }

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px', fontFamily: 'system-ui, sans-serif' }}>
      <h1 style={{ fontSize: 22, fontWeight: 500, marginBottom: 4 }}>Connected services</h1>
      <p style={{ fontSize: 14, color: '#666', marginBottom: 24 }}>
        You control which services your health agent can access. Disconnect anytime.
      </p>

      {services.map(svc => (
        <div key={svc.id} style={{
          border: '0.5px solid #e0e0e0', borderRadius: 12,
          padding: '16px 20px', marginBottom: 12, background: '#fff',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center'
        }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 500 }}>{svc.name}</div>
            <div style={{ fontSize: 13, color: '#666', marginTop: 2 }}>{svc.desc}</div>
            <span style={{
              display: 'inline-block', marginTop: 6,
              padding: '2px 10px', borderRadius: 20, fontSize: 11,
              background: '#E6F1FB', color: '#185FA5', border: '0.5px solid #85B7EB'
            }}>
              {svc.scope}
            </span>
          </div>
          {connected[svc.id] ? (
            <button
              onClick={() => disconnect(svc.id)}
              style={{
                padding: '7px 14px', borderRadius: 8, fontSize: 13,
                border: '0.5px solid #F09595', background: '#FCEBEB',
                color: '#791F1F', cursor: 'pointer'
              }}
            >
              Disconnect
            </button>
          ) : (
            <button
              onClick={() => connect(svc.id)}
              style={{
                padding: '7px 14px', borderRadius: 8, fontSize: 13,
                border: '0.5px solid #5DCAA5', background: '#E1F5EE',
                color: '#085041', cursor: 'pointer'
              }}
            >
              Connect
            </button>
          )}
        </div>
      ))}

      <div style={{
        marginTop: 24, padding: '14px 16px',
        background: '#F1EFE8', borderRadius: 8,
        fontSize: 13, color: '#444'
      }}>
        <strong>Your privacy:</strong> Raw health data is never stored outside your
        Auth0-protected session. The AI only sees summaries it generates itself.
        Write actions (booking, sharing) always require biometric re-verification.
      </div>
    </div>
  )
}
