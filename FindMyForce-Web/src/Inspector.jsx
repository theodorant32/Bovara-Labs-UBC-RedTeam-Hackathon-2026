import { useEffect, useRef } from 'react'
import { CSS_COLORS } from './data'

const PIPELINE = [
  { label: 'DATA', icon: '📡' },
  { label: 'CLASSIFY', icon: '🔍' },
  { label: 'ASSOCIATE', icon: '🔗' },
  { label: 'GEOLOCATE', icon: '📍' },
  { label: 'TRACK', icon: '📊' },
  { label: 'COP', icon: '🖥️' },
]

export default function Inspector({ track, pipelineStep }) {
  const waveRef = useRef(null)

  useEffect(() => {
    if (!track || !waveRef.current) return
    const wc  = waveRef.current
    const ctx = wc.getContext('2d')
    wc.width  = wc.offsetWidth || 220
    wc.height = wc.offsetHeight || 55
    const w = wc.width, h = wc.height
    ctx.fillStyle = '#020c11'
    ctx.fillRect(0, 0, w, h)
    const c = CSS_COLORS[track.cls]
    ctx.strokeStyle = c
    ctx.lineWidth   = 1.5
    ctx.shadowColor = c
    ctx.shadowBlur  = 4
    ctx.beginPath()
    for (let i = 0; i < 128; i++) {
      const x = (i / 128) * w
      let y
      if (track.cls === 'hostile') y = h/2 + (Math.random()-0.5)*h*0.85
      else if (track.cls === 'friendly') y = h/2 + Math.sin(i*0.45)*h*0.3 + (Math.random()-0.5)*h*0.08
      else y = h/2 + (Math.random()-0.5)*h*0.55
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
    }
    ctx.stroke()
  }, [track])

  const row = (k, v, cls) => (
    <div style={{ display:'flex', justifyContent:'space-between', padding:'3px 0',
      borderBottom:'1px solid rgba(10,32,48,0.5)', fontSize:10 }}>
      <span style={{ color:'var(--dim)' }}>{k}</span>
      <span style={{ color: cls ? CSS_COLORS[cls] : 'var(--text)', textAlign:'right' }}>{v}</span>
    </div>
  )

  const section = (title, children) => (
    <div style={{ marginBottom:16, padding:'10px', background:'rgba(10,32,48,0.15)', borderRadius:4, border:'1px solid rgba(10,32,48,0.4)' }}>
      <div style={{ fontFamily:'var(--display)', fontSize:8, letterSpacing:3, color:'var(--glow)',
        borderBottom:'1px solid var(--border)', paddingBottom:6, marginBottom:8, textShadow:'0 0 8px var(--glow)' }}>{title}</div>
      {children}
    </div>
  )

  return (
    <div style={{ background:'var(--panel)', borderLeft:'1px solid var(--border)',
      display:'flex', flexDirection:'column', overflow:'hidden', width:260 }}>

      <div style={{ padding:'10px 12px', borderBottom:'1px solid var(--border)',
        fontFamily:'var(--display)', fontSize:9, letterSpacing:2, color:'var(--dim)' }}>
        TRACK INSPECTOR
      </div>

      <div style={{ padding:12, flex:1, overflowY:'auto' }}>
        {!track ? (
          <div style={{ color:'var(--dim)', textAlign:'center', marginTop:50, fontSize:10, lineHeight:2 }}>
            SELECT A TRACK<br/>TO INSPECT
          </div>
        ) : (
          <>
            {section('IDENTIFICATION', <>
              {row('Track ID',    track.id)}
              {row('Class',       track.cls.toUpperCase(), track.cls)}
              {row('Signal Type', track.type)}
              {row('Modulation',  track.mod)}
              {row('Confidence',  `${Math.round(track.conf*100)}%`)}
              {row('Status',      track.stale ? 'STALE' : 'ACTIVE')}
            </>)}
            {section('GEOLOCATION', <>
              {row('Latitude',     `${track.lat.toFixed(4)}°`)}
              {row('Longitude',    `${track.lon.toFixed(4)}°`)}
              {row('CEP ±',        `${track.cep} m`)}
              {row('Observations', track.obs)}
            </>)}
            {section('RF PARAMETERS', <>
              {row('RSSI', `${track.rssi} dBm`)}
              {row('SNR',  `${track.snr > 0 ? '+' : ''}${track.snr} dB`)}
            </>)}
            {section('IQ SNAPSHOT',
              <canvas ref={waveRef} style={{ width:'100%', height:55,
                background:'#020c11', border:'1px solid var(--border)', borderRadius:2, marginTop:6 }} />
            )}
          </>
        )}
      </div>

      {/* Pipeline strip */}
      <div style={{ borderTop:'1px solid var(--border)', padding:'10px 12px',
        display:'flex', gap:5, flexWrap:'wrap', background:'rgba(2,8,16,0.5)' }}>
        {PIPELINE.map((step, i) => {
          const done   = i < pipelineStep
          const active = i === pipelineStep
          return (
            <span key={step.label} style={{
              fontSize:7, padding:'4px 7px', borderRadius:3, letterSpacing:1,
              border: done   ? '1px solid var(--friendly)' :
                      active ? '1px solid var(--glow)'     : '1px solid var(--border)',
              color:  done   ? 'var(--friendly)' :
                      active ? 'var(--glow)'     : 'var(--dim)',
              background: active ? 'rgba(0,245,212,0.08)' :
                          done   ? 'rgba(0,255,136,0.05)' : 'transparent',
              transition:'all 0.25s ease',
              boxShadow: active ? `0 0 12px ${done ? 'var(--friendly)' : 'var(--glow)'}30` : 'none',
              display:'flex', alignItems:'center', gap:4,
            }}>
              <span style={{ opacity:0.7 }}>{step.icon}</span>
              {step.label}
            </span>
          )
        })}
      </div>
    </div>
  )
}
