import { useEffect, useState } from 'react'
import { useRouter } from 'next/router'

export default function StepUpCallback() {
  const router = useRouter()
  const [status, setStatus] = useState('Verifying...')

  useEffect(() => {
    const { code, state } = router.query
    if (!code || !state) return

    const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    fetch(`${API}/stepup/callback?code=${code}&state=${state}`)
      .then(r => r.json())
      .then(data => {
        if (data.status === 'verified') {
          setStatus(`Verified! Write access granted for ${data.window_seconds / 60} minutes.`)
          setTimeout(() => router.push('/'), 2000)
        } else {
          setStatus('Verification failed. Please try again.')
        }
      })
      .catch(() => setStatus('Error during verification.'))
  }, [router.query])

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', height: '100vh', fontFamily: 'system-ui, sans-serif'
    }}>
      <div style={{
        padding: '32px 40px', borderRadius: 12,
        border: '0.5px solid #e0e0e0', background: '#fff',
        textAlign: 'center', maxWidth: 360
      }}>
        <div style={{ fontSize: 32, marginBottom: 16 }}>
          {status.includes('Verified') ? '✓' : status.includes('Error') || status.includes('failed') ? '✗' : '⟳'}
        </div>
        <p style={{ fontSize: 15, color: '#333', margin: 0 }}>{status}</p>
        {status.includes('Verified') && (
          <p style={{ fontSize: 13, color: '#666', marginTop: 8 }}>Redirecting back to your dashboard...</p>
        )}
      </div>
    </div>
  )
}
