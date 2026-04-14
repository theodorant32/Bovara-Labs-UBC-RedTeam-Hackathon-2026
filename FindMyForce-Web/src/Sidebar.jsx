import { useState } from 'react'
import { CSS_COLORS } from './data'

const s = {
  sidebar: {
    background:'var(--panel)', borderRight:'1px solid var(--border)',
    display:'flex', flexDirection:'column', overflow:'hidden', width:260,
    boxShadow:'4px 0 20px rgba(0,0,0,0.3)',
  },
  head: {
    padding:'12px 14px', borderBottom:'1px solid var(--border)',
    fontFamily:'var(--display)', fontSize:9, letterSpacing:3, color:'var(--dim)',
    display:'flex', justifyContent:'space-between', alignItems:'center',
    background:'linear-gradient(90deg, rgba(0,245,212,0.03) 0%, transparent 100%)',
  },
  badge: {
    background:'rgba(0,245,212,0.12)', border:'1px solid var(--glow)',
    color:'var(--glow)', padding:'2px 8px', borderRadius:3, fontSize:10,
    boxShadow:'0 0 8px rgba(0,245,212,0.2)', fontWeight:700,
  },
  filterRow: { display:'flex', borderBottom:'1px solid var(--border)', background:'rgba(2,8,16,0.5)' },
  list: { overflowY:'auto', flex:1, padding:'4px 0' },
}

const FILTERS = ['all','friendly','hostile','unknown','civilian']
const LABELS  = ['ALL','FRD','HST','UNK','CIV']

export default function Sidebar({ tracks, selectedId, onSelect }) {
  const [filter, setFilter] = useState('all')

  const visible = tracks.filter(t => filter === 'all' || t.cls === filter)

  return (
    <div style={s.sidebar}>
      <div style={s.head}>
        EMITTER TRACKS
        <span style={s.badge}>{visible.length}</span>
      </div>

      <div style={s.filterRow}>
        {FILTERS.map((f, i) => (
          <button key={f} onClick={() => setFilter(f)} style={{
            flex:1, padding:'6px 2px', textAlign:'center', fontSize:8,
            letterSpacing:1, cursor:'pointer', border:'none', background:'none',
            color: filter === f ? 'var(--glow)' : CSS_COLORS[f] || 'var(--dim)',
            borderBottom: filter === f ? '2px solid var(--glow)' : '2px solid transparent',
            transition:'color 0.2s',
          }}>{LABELS[i]}</button>
        ))}
      </div>

      <div style={s.list}>
        {visible.map(t => <TrackRow key={t.id} track={t} selected={t.id === selectedId} onSelect={onSelect} />)}
      </div>
    </div>
  )
}

function TrackRow({ track: t, selected, onSelect }) {
  const cp = Math.round(t.conf * 100)
  const cc = cp > 80 ? 'var(--friendly)' : cp > 55 ? 'var(--unknown)' : 'var(--hostile)'
  const c  = CSS_COLORS[t.cls]

  return (
    <div onClick={() => onSelect(t.id)} style={{
      padding:'10px 14px', borderBottom:'1px solid rgba(10,32,48,0.4)', cursor:'pointer',
      background: selected ? 'rgba(0,245,212,0.08)' : 'transparent',
      borderLeft: `4px solid ${c}`,
      transition:'all 0.15s ease',
      position:'relative',
    }}
    onMouseEnter={e => {
      if (!selected) {
        e.currentTarget.style.background = 'rgba(0,245,212,0.04)'
        e.currentTarget.style.paddingLeft = '16px'
      }
    }}
    onMouseLeave={e => {
      if (!selected) {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.paddingLeft = '10px'
      }
    }}
    >
      {/* Signal strength indicator bar on right */}
      <div style={{
        position:'absolute', right:0, top:0, bottom:0, width:3,
        background: t.snr > 10 ? 'var(--friendly)' : t.snr > 0 ? 'var(--unknown)' : 'var(--hostile)',
        opacity: Math.min(1, (t.snr + 20) / 30),
      }} />

      <div style={{ display:'flex', justifyContent:'space-between', fontFamily:'var(--display)', fontSize:10, marginBottom:5, alignItems:'center' }}>
        <span style={{ fontWeight:700, color:'var(--text)', textShadow:'0 0 8px rgba(255,255,255,0.1)' }}>{t.id}</span>
        <span style={{ fontSize:7, padding:'2px 6px', borderRadius:3, letterSpacing:1,
          background:`${c}15`, color:c, border:`1px solid ${c}40`,
          boxShadow:`0 0 8px ${c}20`, fontWeight:600 }}>
          {t.cls.toUpperCase()}
        </span>
      </div>
      <div style={{ color:'var(--dim)', fontSize:9, lineHeight:1.8 }}>
        <span style={{ color:'var(--text)', fontWeight:500 }}>{t.type}</span>
        <span style={{ marginLeft:8, color:'var(--dim)' }}>|</span>
        <span style={{ marginLeft:8 }}>{t.snr > 0 ? '+' : ''}{t.snr} dB</span>
        <span style={{ marginLeft:6, color:'var(--dim)' }}>•</span>
        <span style={{ marginLeft:6 }}>{t.obs} obs</span>
      </div>
      {/* Confidence bar with gradient */}
      <div style={{ height:3, background:'rgba(10,32,48,0.6)', borderRadius:2, marginTop:6, overflow:'hidden' }}>
        <div style={{
          height:'100%', width:`${cp}%`,
          background: `linear-gradient(90deg, ${c}60, ${c})`,
          borderRadius:2,
          transition:'width 0.4s ease',
          boxShadow:`0 0 10px ${c}60`,
        }} />
      </div>
    </div>
  )
}
