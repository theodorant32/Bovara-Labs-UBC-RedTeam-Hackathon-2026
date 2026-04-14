import { useState, useEffect, useCallback } from 'react'
import Globe     from './Globe'
import MapView   from './MapView'
import Sidebar   from './Sidebar'
import Inspector from './Inspector'
import { INITIAL_TRACKS, CSS_COLORS } from './data'

// In dev, Vite proxies /tracks etc. to localhost:5000
// In production, set this to the actual API host
const API_BASE = ''

function vanTime() {
  return new Date().toLocaleTimeString('en-CA', {
    timeZone: 'America/Vancouver',
    hour12: false, hour:'2-digit', minute:'2-digit', second:'2-digit'
  }) + ' PT'
}

// Animated radar logo component
const Logo = () => (
  <div style={{ display:'flex', alignItems:'center', gap:10, marginRight:14 }}>
    <div style={{
      width:28, height:28, position:'relative',
      border:'2px solid var(--glow)', borderRadius:'50%',
      boxShadow:'0 0 12px rgba(0,245,212,0.4), inset 0 0 10px rgba(0,245,212,0.2)',
      background:'radial-gradient(circle, rgba(0,245,212,0.1) 0%, transparent 70%)',
      overflow:'hidden',
    }}>
      {/* Rotating radar sweep */}
      <div style={{
        position:'absolute', top:'50%', left:'50%',
        width:'60%', height:2,
        background:`linear-gradient(90deg, var(--glow) 0%, transparent 100%)`,
        transformOrigin:'left center',
        animation:'radarSpin 2s linear infinite',
        boxShadow:'0 0 8px var(--glow)',
      }} />
      <div style={{
        position:'absolute', top:'50%', left:'50%',
        width:5, height:5, background:'var(--glow)', borderRadius:'50%',
        transform:'translate(-50%, -50%)',
        boxShadow:'0 0 10px var(--glow)',
      }} />
      <style>{`@keyframes radarSpin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  </div>
)

export default function App() {
  const [tracks,       setTracks]       = useState(INITIAL_TRACKS)
  const [selectedId,   setSelectedId]   = useState(null)
  const [clock,        setClock]        = useState(vanTime)
  const [pipelineStep, setPipelineStep] = useState(6)
  const [view,         setView]         = useState('map')   // 'globe' or 'map'
  const [connected,    setConnected]    = useState(false)
  const [evalResult,   setEvalResult]   = useState(null)
  const [evalLoading,  setEvalLoading]  = useState(false)
  const [serverStatus, setServerStatus] = useState(null)
  const [showDataWarning, setShowDataWarning] = useState(true)

  const selectedTrack = tracks.find(t => t.id === selectedId) || null

  // Clock tick
  useEffect(() => {
    const iv = setInterval(() => setClock(vanTime()), 1000)
    return () => clearInterval(iv)
  }, [])

  // Animate pipeline when a track is selected
  const handleSelect = useCallback(id => {
    setSelectedId(id)
    setPipelineStep(0)
    let step = 0
    const iv = setInterval(() => {
      step++
      setPipelineStep(step)
      if (step >= 6) clearInterval(iv)
    }, 300)
  }, [])

  // Poll backend for live tracks
  useEffect(() => {
    let active = true

    const fetchTracks = async () => {
      try {
        const res = await fetch(`${API_BASE}/tracks`)
        if (!res.ok) throw new Error('fetch failed')
        const data = await res.json()
        if (active && data.length > 0) {
          setTracks(data)
          setConnected(true)
        }
      } catch {
        // Backend not available, keep mock data
        if (active) setConnected(false)
      }
    }

    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/status`)
        if (res.ok) {
          const data = await res.json()
          if (active) setServerStatus(data)
        }
      } catch { /* ignore */ }
    }

    fetchTracks()
    fetchStatus()
    const iv = setInterval(() => { fetchTracks(); fetchStatus() }, 5000)
    return () => { active = false; clearInterval(iv) }
  }, [])

  // Mock live updates when not connected to backend
  useEffect(() => {
    if (connected) return
    const iv = setInterval(() => {
      setTracks(prev => prev.map(t => ({
        ...t,
        lat: t.lat + (Math.random()-0.5) * 0.002,
        lon: t.lon + (Math.random()-0.5) * 0.002,
        snr: Math.max(-20, Math.min(18, t.snr + (Math.random()-0.5)*0.3)),
      })))
    }, 3000)
    return () => clearInterval(iv)
  }, [connected])

  const runEval = async () => {
    setEvalLoading(true)
    try {
      const res = await fetch(`${API_BASE}/eval/run`, { method: 'POST' })
      const data = await res.json()
      setEvalResult(data)
      // Refresh tracks after eval
      const tRes = await fetch(`${API_BASE}/tracks`)
      if (tRes.ok) setTracks(await tRes.json())
    } catch (e) {
      setEvalResult({ error: `Failed: ${e.message}` })
    }
    setEvalLoading(false)
  }

  const counts = {
    total:    tracks.length,
    friendly: tracks.filter(t => t.cls === 'friendly').length,
    hostile:  tracks.filter(t => t.cls === 'hostile').length,
    unknown:  tracks.filter(t => t.cls === 'unknown').length,
    civilian: tracks.filter(t => t.cls === 'civilian').length,
  }

  return (
    <div className="app-container" style={{ display:'flex', flexDirection:'column', height:'100vh', overflow:'hidden' }}>

      {/* HEADER */}
      <header style={{
        height:52, background:'var(--panel)', borderBottom:'1px solid var(--border)',
        display:'flex', alignItems:'center', padding:'0 18px', gap:16,
        flexShrink:0, position:'relative', zIndex:10,
        boxShadow:'0 2px 20px rgba(0,245,212,0.1)',
      }}>
        <Logo />
        <div style={{ display:'flex', flexDirection:'column', gap:0 }}>
          <div style={{ fontFamily:'var(--display)', fontWeight:700, fontSize:14,
            letterSpacing:6, color:'var(--glow)', textShadow:'0 0 20px var(--glow)' }}>
            FINDMYFORCE
          </div>
          <div style={{ fontSize:8, color:'var(--dim)', letterSpacing:3, marginLeft:1 }}>
            COMMON OPERATING PICTURE
          </div>
        </div>

        {[
          ['TRACKS',   counts.total,    'var(--text)'],
          ['FRD', counts.friendly, 'var(--friendly)'],
          ['HST',  counts.hostile,  'var(--hostile)'],
          ['UNK',  counts.unknown,  'var(--unknown)'],
          ['CIV', counts.civilian, 'var(--civilian)'],
        ].map(([label, val, color]) => (
          <div key={label} style={{ display:'flex', gap:'0 14px', alignItems:'center', padding:'0 8px',
            background:'rgba(10,32,48,0.3)', borderRadius:4, border:'1px solid rgba(10,32,48,0.5)' }}>
            <div style={{ width:1, height:18, background:'var(--border)' }} />
            <div style={{ display:'flex', flexDirection:'column', gap:0, minWidth:36 }}>
              <span style={{ fontSize:7, color:'var(--dim)', letterSpacing:1, textAlign:'center' }}>{label}</span>
              <span style={{ fontSize:14, fontWeight:700, color, textShadow:`0 0 8px ${color}40` }}>{val}</span>
            </div>
          </div>
        ))}

        {/* View toggle */}
        <div style={{ marginLeft: 'auto', display:'flex', gap:6, background:'rgba(2,8,16,0.4)', padding:3, borderRadius:4, border:'1px solid var(--border)' }}>
          {['map', 'globe'].map(v => (
            <button key={v} onClick={() => setView(v)} style={{
              padding:'5px 12px', fontSize:8, letterSpacing:2, cursor:'pointer',
              border: 'none',
              background: view === v ? 'rgba(0,245,212,0.15)' : 'transparent',
              color: view === v ? 'var(--glow)' : 'var(--dim)',
              borderRadius: 3, fontFamily: 'inherit', fontWeight:600,
              transition:'all 0.2s ease',
              boxShadow: view === v ? '0 0 10px rgba(0,245,212,0.2)' : 'none',
            }}>{v.toUpperCase()}</button>
          ))}
        </div>

        <div style={{ display:'flex', alignItems:'center', gap:12 }}>
          {/* Connection indicator */}
          <div style={{
            width:8, height:8, borderRadius:'50%',
            background: connected ? 'var(--friendly)' : 'var(--hostile)',
            boxShadow: `0 0 8px ${connected ? 'var(--friendly)' : 'var(--hostile)'}`,
            animation:'blink 2s infinite',
          }} />
          <div style={{ fontFamily:'var(--display)', fontSize:10, color:'var(--dim)' }}>
            {connected ? 'LIVE' : 'DEMO'}
          </div>
          <div style={{ fontFamily:'var(--display)', fontSize:12, color:'var(--glow)', letterSpacing:2 }}>
            {clock}
          </div>
        </div>

        <style>{`@keyframes blink{0%,100%{opacity:1}50%{opacity:0.2}}`}</style>
      </header>

      {/* Data Warning Banner */}
      {showDataWarning && !connected && (
        <div style={{
          background:'rgba(255,184,0,0.08)', borderBottom:'1px solid rgba(255,184,0,0.3)',
          padding:'8px 16px', display:'flex', alignItems:'center', gap:12,
          fontSize:10, color:'var(--unknown)', justifyContent:'center',
        }}>
          <span style={{ fontWeight:600 }}>⚠ DEMO MODE</span>
          <span>Running with mock data. Connect to API backend for live classification.</span>
          <button onClick={() => setShowDataWarning(false)} style={{
            marginLeft:'auto', background:'transparent', border:'1px solid var(--unknown)',
            color:'var(--unknown)', padding:'2px 8px', cursor:'pointer', fontSize:9,
            borderRadius:2, fontFamily:'inherit',
          }}>DISMISS</button>
        </div>
      )}

      {/* MAIN */}
      <div style={{ flex:1, display:'flex', overflow:'hidden' }}>
        <Sidebar tracks={tracks} selectedId={selectedId} onSelect={handleSelect} />

        <div style={{ flex:1, display:'flex', flexDirection:'column', overflow:'hidden' }}>
          {/* Visualization area */}
          <div style={{ flex:1, position:'relative', overflow:'hidden' }}>
            {view === 'globe'
              ? <Globe tracks={tracks} onSelectTrack={handleSelect} />
              : <MapView tracks={tracks} onSelectTrack={handleSelect} />
            }
          </div>

          {/* Bottom bar: eval controls + server info */}
          <div style={{
            height: evalResult ? 'auto' : 36,
            minHeight: 36,
            background:'var(--panel)', borderTop:'1px solid var(--border)',
            display:'flex', flexDirection: 'column', padding:'0 14px',
            fontSize:10, flexShrink:0,
          }}>
            <div style={{ display:'flex', alignItems:'center', gap:14, height:36 }}>
              {connected && (
                <button onClick={runEval} disabled={evalLoading} style={{
                  padding:'4px 12px', fontSize:9, letterSpacing:1, cursor: evalLoading ? 'wait' : 'pointer',
                  border:'1px solid var(--glow)', background:'rgba(0,245,212,0.08)',
                  color:'var(--glow)', borderRadius:2, fontFamily:'inherit',
                  opacity: evalLoading ? 0.5 : 1,
                }}>
                  {evalLoading ? 'RUNNING...' : 'RUN EVAL'}
                </button>
              )}

              {serverStatus && (
                <>
                  <span style={{ color:'var(--dim)' }}>
                    SIM: <span style={{ color:'var(--text)' }}>{serverStatus.simulation_state || '?'}</span>
                  </span>
                  <span style={{ color:'var(--dim)' }}>
                    EVAL: <span style={{ color: serverStatus.evaluation_open ? 'var(--friendly)' : 'var(--hostile)' }}>
                      {serverStatus.evaluation_open ? 'OPEN' : 'CLOSED'}
                    </span>
                  </span>
                </>
              )}

              {evalResult && !evalResult.error && (
                <span style={{ color:'var(--dim)' }}>
                  SCORE: <span style={{ color:'var(--glow)', fontSize:12 }}>{evalResult.total_score?.toFixed(1)}</span>
                  {' '}| CLASS: <span style={{ color:'var(--text)' }}>{evalResult.classification_score?.toFixed(1)}</span>
                  {' '}| GEO: <span style={{ color:'var(--text)' }}>{evalResult.geolocation_score?.toFixed(1)}</span>
                  {' '}| NOVELTY: <span style={{ color:'var(--text)' }}>{evalResult.novelty_detection_score?.toFixed(1)}</span>
                  {' '}| ATTEMPT #{evalResult.attempt_number}
                  {evalResult.is_best && <span style={{ color:'var(--friendly)', marginLeft:6 }}>BEST</span>}
                </span>
              )}

              {evalResult?.error && (
                <span style={{ color:'var(--hostile)' }}>{evalResult.error}</span>
              )}
            </div>

            {/* Detailed eval results */}
            {evalResult && !evalResult.error && evalResult.per_class_scores && (
              <div style={{
                borderTop:'1px solid var(--border)', padding:'8px 0', marginBottom:8,
                display:'flex', gap:12, flexWrap:'wrap',
              }}>
                <div style={{ color:'var(--dim)', fontSize:9, width:'100%', marginBottom:4, letterSpacing:1 }}>
                  PER-CLASS BREAKDOWN
                </div>
                {evalResult.per_class_scores.map((cls, i) => (
                  <div key={i} style={{
                    padding:'3px 8px', border:'1px solid var(--border)', borderRadius:2,
                    fontSize:9, color:'var(--text)',
                  }}>
                    <span style={{ color: CSS_COLORS[
                      ['Radar-Altimeter','Satcom','short-range'].includes(cls.label) ? 'friendly'
                      : cls.label === 'AM radio' ? 'civilian'
                      : 'hostile'
                    ] }}>{cls.label}</span>
                    {' '}{cls.score?.toFixed(1) ?? '?'}
                  </div>
                ))}
                <div style={{ color:'var(--dim)', fontSize:9 }}>
                  COVERAGE: {evalResult.coverage?.toFixed(1)}%
                  {' '}| CEP: {evalResult.average_cep_meters?.toFixed(0)}m
                  {' '}| CORRECT: {evalResult.correct_classifications}/{evalResult.total_observations}
                </div>
              </div>
            )}
          </div>
        </div>

        <Inspector track={selectedTrack} pipelineStep={pipelineStep} />
      </div>
    </div>
  )
}
