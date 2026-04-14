import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { THREE_COLORS, CSS_COLORS, RECEIVERS } from './data'

// Convert lat/lon to 3D point on unit sphere
function latLonTo3D(lat, lon, r = 1.02) {
  const phi   = (90 - lat)  * (Math.PI / 180)
  const theta = (lon + 180) * (Math.PI / 180)
  return new THREE.Vector3(
    -r * Math.sin(phi) * Math.cos(theta),
     r * Math.cos(phi),
     r * Math.sin(phi) * Math.sin(theta)
  )
}

function buildGlobeTexture() {
  const tc = document.createElement('canvas')
  tc.width = 2048; tc.height = 1024
  const ctx = tc.getContext('2d')
  ctx.fillStyle = '#020d18'
  ctx.fillRect(0, 0, 2048, 1024)
  ctx.strokeStyle = 'rgba(0,180,140,0.12)'; ctx.lineWidth = 1
  for (let lat = -80; lat <= 80; lat += 20) {
    const y = ((90 - lat) / 180) * 1024
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(2048, y); ctx.stroke()
  }
  for (let lon = -180; lon <= 180; lon += 20) {
    const x = ((lon + 180) / 360) * 2048
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, 1024); ctx.stroke()
  }
  ctx.strokeStyle = 'rgba(0,245,212,0.2)'; ctx.lineWidth = 1.5
  ctx.beginPath(); ctx.moveTo(0, 512); ctx.lineTo(2048, 512); ctx.stroke()
  return new THREE.CanvasTexture(tc)
}

export default function Globe({ tracks, onSelectTrack }) {
  const mountRef   = useRef(null)
  const sceneRef   = useRef(null)
  const markersRef = useRef({})
  const stateRef   = useRef({ rotX: -0.86, rotY: -0.99, velX: 0, velY: 0, isDragging: false, prevMouse: { x:0, y:0 } })

  // ── Build scene once ──
  useEffect(() => {
    const wrap = mountRef.current
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(window.devicePixelRatio)
    wrap.appendChild(renderer.domElement)

    const scene  = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000)
    camera.position.z = 1.6
    sceneRef.current  = { scene, camera, renderer, globe: null }

    // Globe
    const globe = new THREE.Mesh(
      new THREE.SphereGeometry(1, 64, 64),
      new THREE.MeshPhongMaterial({ map: buildGlobeTexture(), transparent: true, opacity: 0.92, shininess: 8 })
    )
    scene.add(globe)
    sceneRef.current.globe = globe

    // Atmosphere
    scene.add(new THREE.Mesh(
      new THREE.SphereGeometry(1.04, 64, 64),
      new THREE.MeshPhongMaterial({ color: 0x00ffe7, transparent: true, opacity: 0.06 })
    ))

    // Lights
    scene.add(new THREE.AmbientLight(0x223344, 1.2))
    const sun = new THREE.DirectionalLight(0x88ccff, 1.4)
    sun.position.set(5, 3, 5); scene.add(sun)

    // Stars
    const starPos = []
    for (let i = 0; i < 3000; i++) {
      const phi   = Math.acos(2 * Math.random() - 1)
      const theta = Math.random() * Math.PI * 2
      const r     = 8 + Math.random() * 4
      starPos.push(r*Math.sin(phi)*Math.cos(theta), r*Math.sin(phi)*Math.sin(theta), r*Math.cos(phi))
    }
    const starGeo = new THREE.BufferGeometry()
    starGeo.setAttribute('position', new THREE.Float32BufferAttribute(starPos, 3))
    scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0x667788, size: 0.02 })))

    // Resize
    const resize = () => {
      const w = wrap.clientWidth, h = wrap.clientHeight
      renderer.setSize(w, h)
      camera.aspect = w / h
      camera.updateProjectionMatrix()
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(wrap)

    // Mouse controls
    const onDown = e => {
      stateRef.current.isDragging = true
      stateRef.current.prevMouse  = { x: e.clientX, y: e.clientY }
      stateRef.current.velX = stateRef.current.velY = 0
    }
    const onUp   = () => { stateRef.current.isDragging = false }
    const onMove = e => {
      const s = stateRef.current
      if (!s.isDragging) return
      s.velX = (e.clientY - s.prevMouse.y) * 0.003
      s.velY = (e.clientX - s.prevMouse.x) * 0.003
      s.rotX += s.velX; s.rotY += s.velY
      s.prevMouse = { x: e.clientX, y: e.clientY }
    }
    const onWheel = e => {
      camera.position.z = Math.max(1.5, Math.min(5, camera.position.z + e.deltaY * 0.003))
    }

    renderer.domElement.addEventListener('mousedown', onDown)
    renderer.domElement.addEventListener('wheel',     onWheel)
    window.addEventListener('mouseup',   onUp)
    window.addEventListener('mousemove', onMove)

    // Raycaster for clicks
    const raycaster = new THREE.Raycaster()
    const mouse2d   = new THREE.Vector2()
    const onClick = e => {
      const rect = renderer.domElement.getBoundingClientRect()
      mouse2d.x =  ((e.clientX - rect.left) / rect.width)  * 2 - 1
      mouse2d.y = -((e.clientY - rect.top)  / rect.height) * 2 + 1
      raycaster.setFromCamera(mouse2d, camera)
      const dots = Object.values(markersRef.current).map(m => m.dot)
      const hits = raycaster.intersectObjects(dots)
      if (hits.length > 0) {
        const hit   = hits[0].object
        const entry = Object.values(markersRef.current).find(m => m.dot === hit)
        if (entry) onSelectTrack(entry.track.id)
      }
    }
    renderer.domElement.addEventListener('click', onClick)

    // Animation loop
    let t = 0, rafId
    const animate = () => {
      rafId = requestAnimationFrame(animate)
      t += 0.016
      const s = stateRef.current
      if (!s.isDragging) {
        s.velX *= 0.94; s.velY *= 0.94
        s.rotX += s.velX; s.rotY += s.velY
        // no auto-rotate — zoomed in on Vancouver
      }
      globe.rotation.x = s.rotX
      globe.rotation.y = s.rotY
      Object.values(markersRef.current).forEach(({ group, ring, track }) => {
        group.rotation.copy(globe.rotation)
        const pulse = 1 + 0.3 * Math.sin(t * 2 + track.lat)
        ring.scale.setScalar(track.stale ? 0.5 : pulse)
        ring.material.opacity = track.stale ? 0.2 : 0.4 + 0.3 * Math.sin(t * 2 + track.lat)
      })
      renderer.render(scene, camera)
    }
    animate()

    return () => {
      cancelAnimationFrame(rafId)
      ro.disconnect()
      window.removeEventListener('mouseup',   onUp)
      window.removeEventListener('mousemove', onMove)
      renderer.dispose()
      if (wrap.contains(renderer.domElement)) wrap.removeChild(renderer.domElement)
    }
  }, [])

  // ── Update markers when tracks change ──
  useEffect(() => {
    const { scene, globe } = sceneRef.current || {}
    if (!scene || !globe) return

    // Remove old markers
    Object.values(markersRef.current).forEach(({ group }) => scene.remove(group))
    markersRef.current = {}

    tracks.forEach(track => {
      const color = THREE_COLORS[track.cls] || 0xffffff
      const group = new THREE.Group()

      const dot = new THREE.Mesh(
        new THREE.SphereGeometry(0.014, 12, 12),
        new THREE.MeshPhongMaterial({ color, emissive: color, emissiveIntensity: 0.8 })
      )
      group.add(dot)

      const ring = new THREE.Mesh(
        new THREE.RingGeometry(0.018, 0.026, 32),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.6, side: THREE.DoubleSide })
      )
      group.add(ring)

      if (track.cls === 'hostile') {
        const beam = new THREE.Mesh(
          new THREE.CylinderGeometry(0.002, 0.002, 0.15, 8),
          new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5 })
        )
        beam.position.y = 0.075
        group.add(beam)
      }

      const pos = latLonTo3D(track.lat, track.lon)
      group.position.copy(pos)
      group.lookAt(new THREE.Vector3(0, 0, 0))
      group.rotateX(Math.PI / 2)
      group.rotation.copy(globe.rotation)

      scene.add(group)
      markersRef.current[track.id] = { group, ring, dot, track }
    })
  }, [tracks])

  // ── Receiver markers (diamonds) ──
  useEffect(() => {
    const { scene, globe } = sceneRef.current || {}
    if (!scene || !globe) return
    RECEIVERS.forEach(rx => {
      const group = new THREE.Group()
      // Diamond shape using octahedron
      const geo = new THREE.OctahedronGeometry(0.012)
      const mat = new THREE.MeshPhongMaterial({ color: 0x00f5d4, emissive: 0x00f5d4, emissiveIntensity: 0.6 })
      group.add(new THREE.Mesh(geo, mat))
      // Label ring
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(0.016, 0.02, 4),
        new THREE.MeshBasicMaterial({ color: 0x00f5d4, transparent: true, opacity: 0.4, side: THREE.DoubleSide })
      )
      group.add(ring)
      const pos = latLonTo3D(rx.lat, rx.lon, 1.015)
      group.position.copy(pos)
      group.lookAt(new THREE.Vector3(0, 0, 0))
      group.rotateX(Math.PI / 2)
      group.rotation.copy(globe.rotation)
      group.userData.isReceiver = true
      scene.add(group)
    })
  }, [])


  return (
    <div ref={mountRef} style={{
      position: 'relative', width: '100%', height: '100%',
      background: 'radial-gradient(ellipse at center, #020f1a 0%, #010508 100%)',
      cursor: 'grab',
    }}>
      {/* Corner brackets */}
      {[['top:8px','left:8px','2px 0 0 2px'],['top:8px','right:8px','2px 2px 0 0'],
        ['bottom:8px','left:8px','0 0 2px 2px'],['bottom:8px','right:8px','0 2px 2px 0']
      ].map(([t,l,bw], i) => (
        <div key={i} style={{
          position:'absolute', width:18, height:18,
          borderColor:'#00f5d4', borderStyle:'solid', borderWidth:bw,
          opacity:0.4, pointerEvents:'none', zIndex:5,
          ...Object.fromEntries(t.split(',').map(s => s.trim().split(':')))
        }} />
      ))}
      <div style={{
        position:'absolute', bottom:12, left:'50%', transform:'translateX(-50%)',
        fontSize:9, color:'var(--dim)', letterSpacing:1, pointerEvents:'none', zIndex:5
      }}>
        DRAG TO ROTATE · SCROLL TO ZOOM
      </div>
    </div>
  )
}
