import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { CSS_COLORS, RECEIVERS } from './data'

const CENTER = [49.2634, -123.2481]
const ZOOM = 14

export default function MapView({ tracks, onSelectTrack }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const markersRef = useRef({})
  const rxMarkersRef = useRef([])

  // Initialize map once
  useEffect(() => {
    if (mapRef.current) return
    const map = L.map(containerRef.current, {
      center: CENTER,
      zoom: ZOOM,
      zoomControl: false,
      attributionControl: false,
    })

    // Dark tile layer
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
    }).addTo(map)

    L.control.zoom({ position: 'bottomright' }).addTo(map)

    // Draw receiver positions
    RECEIVERS.forEach(rx => {
      const marker = L.circleMarker([rx.lat, rx.lon], {
        radius: 6,
        color: '#00f5d4',
        fillColor: '#00f5d4',
        fillOpacity: 0.3,
        weight: 2,
      }).addTo(map)
      marker.bindTooltip(rx.id, {
        permanent: false,
        direction: 'top',
        className: 'rx-tooltip',
      })
      rxMarkersRef.current.push(marker)
    })

    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  // Update track markers
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    // Remove old markers
    Object.values(markersRef.current).forEach(m => map.removeLayer(m))
    markersRef.current = {}

    tracks.forEach(track => {
      const color = CSS_COLORS[track.cls] || '#ffffff'

      // CEP circle (uncertainty)
      const cepMeters = track.cep || 150
      const cepCircle = L.circle([track.lat, track.lon], {
        radius: cepMeters,
        color: color,
        fillColor: color,
        fillOpacity: 0.06,
        weight: 1,
        dashArray: '4 4',
        opacity: 0.3,
      })

      // Track marker
      const marker = L.circleMarker([track.lat, track.lon], {
        radius: track.stale ? 4 : 7,
        color: color,
        fillColor: color,
        fillOpacity: track.stale ? 0.3 : 0.7,
        weight: 2,
      })

      marker.bindTooltip(
        `<div style="font-family:monospace;font-size:11px;">
          <b>${track.id}</b><br/>
          ${track.type}<br/>
          ${track.cls.toUpperCase()} (${Math.round(track.conf * 100)}%)<br/>
          SNR: ${track.snr > 0 ? '+' : ''}${track.snr} dB
        </div>`,
        { direction: 'top', className: 'track-tooltip' }
      )

      marker.on('click', () => onSelectTrack(track.id))

      // Store layer group for cleanup
      markersRef.current[track.id] = L.layerGroup([cepCircle, marker]).addTo(map)
    })
  }, [tracks, onSelectTrack])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Radar scan line overlay */}
      <div className="scan-line" />
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      <style>{`
        .rx-tooltip {
          background: rgba(5,13,20,0.9) !important;
          border: 1px solid #00f5d4 !important;
          color: #00f5d4 !important;
          font-family: 'Share Tech Mono', monospace !important;
          font-size: 10px !important;
          padding: 2px 6px !important;
        }
        .rx-tooltip::before { border-top-color: #00f5d4 !important; }
        .track-tooltip {
          background: rgba(5,13,20,0.95) !important;
          border: 1px solid #0a2030 !important;
          color: #b0d8e8 !important;
          font-family: 'Share Tech Mono', monospace !important;
          padding: 4px 8px !important;
          box-shadow: 0 0 12px rgba(0,245,212,0.15) !important;
        }
        .track-tooltip::before { border-top-color: #0a2030 !important; }
        .leaflet-container { background: #020810 !important; }
      `}</style>
    </div>
  )
}
