export const CSS_COLORS = {
  friendly: '#00ff88',
  hostile:  '#ff3340',
  unknown:  '#ffb800',
  civilian: '#4da6ff',
}

export const THREE_COLORS = {
  friendly: 0x00ff88,
  hostile:  0xff3340,
  unknown:  0xffb800,
  civilian: 0x4da6ff,
}

// Real receiver positions from GET /config/receivers
// All in Vancouver around UBC / Point Grey
export const RECEIVERS = [
  { id:'RX-01', lat:49.262,  lon:-123.250, sensitivity:-95, timing:50 },
  { id:'RX-02', lat:49.265,  lon:-123.253, sensitivity:-95, timing:50 },
  { id:'RX-03', lat:49.258,  lon:-123.253, sensitivity:-95, timing:50 },
  { id:'RX-04', lat:49.264,  lon:-123.240, sensitivity:-90, timing:30 },
  { id:'RX-05', lat:49.256,  lon:-123.242, sensitivity:-95, timing:50 },
  { id:'RX-06', lat:49.2695, lon:-123.257, sensitivity:-90, timing:30 },
  { id:'RX-07', lat:49.2605, lon:-123.246, sensitivity:-95, timing:50 },
]

// Mock tracks placed around Vancouver.
// Replace with real geolocated positions from your backend:
//   fetch('http://localhost:5000/tracks').then(r => r.json()).then(setTracks)
export const INITIAL_TRACKS = [
  { id:'TRK-001', cls:'friendly', type:'Radar-Altimeter',    mod:'FMCW',
    lat:49.268,  lon:-123.248, rssi:-62, snr:14, conf:0.97, obs:8,  cep:45,  stale:false },
  { id:'TRK-002', cls:'friendly', type:'Satcom',             mod:'BPSK',
    lat:49.253,  lon:-123.235, rssi:-71, snr:8,  conf:0.91, obs:5,  cep:110, stale:false },
  { id:'TRK-003', cls:'hostile',  type:'Airborne-detection', mod:'Pulsed',
    lat:49.275,  lon:-123.262, rssi:-58, snr:6,  conf:0.73, obs:3,  cep:200, stale:false },
  { id:'TRK-004', cls:'unknown',  type:'UNKNOWN-B',          mod:'UNKNOWN',
    lat:49.258,  lon:-123.251, rssi:-80, snr:-4, conf:0.48, obs:2,  cep:480, stale:true  },
  { id:'TRK-005', cls:'friendly', type:'short-range',        mod:'ASK',
    lat:49.261,  lon:-123.239, rssi:-68, snr:10, conf:0.95, obs:11, cep:60,  stale:false },
  { id:'TRK-006', cls:'hostile',  type:'EW-Jammer',          mod:'Jamming',
    lat:49.272,  lon:-123.244, rssi:-55, snr:3,  conf:0.81, obs:6,  cep:150, stale:false },
  { id:'TRK-007', cls:'civilian', type:'AM radio',           mod:'AM-DSB',
    lat:49.249,  lon:-123.258, rssi:-74, snr:4,  conf:0.82, obs:4,  cep:300, stale:false },
  { id:'TRK-008', cls:'hostile',  type:'Airborne-range',     mod:'Pulsed',
    lat:49.265,  lon:-123.231, rssi:-61, snr:5,  conf:0.77, obs:4,  cep:175, stale:false },
  { id:'TRK-009', cls:'hostile',  type:'Air-Ground-MTI',     mod:'Pulsed',
    lat:49.280,  lon:-123.253, rssi:-67, snr:2,  conf:0.69, obs:3,  cep:220, stale:false },
]
