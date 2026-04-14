# Find My Force

**UBC RedTeam Hackathon 2026 — RF Signal Classification & Geolocation System**

A real-time Common Operating Picture (COP) dashboard that classifies RF emitters using machine learning and displays geolocated threats on an interactive tactical map.

---

## Overview

This project was built for the **Find My Force** challenge at the UBC RedTeam Hackathon Series (March 2026). The challenge focused on detecting, classifying, and locating RF emitters from simulated signals intelligence data.

**What it does:**
- **Signal Classification** — ML models classify modulation types (FMCW, Pulsed, CW) and identify emitters (Radar Altimeter, Satcom, Jammers)
- **Geolocation** — TDOA/RSSI-based triangulation from multiple receiver stations
- **Live Visualization** — React dashboard with 2D/3D views and real-time track updates

---

## Quick Start

```bash
# Backend (Python 3.10+)
cd FindMyForce-API
poetry install
python -m findmyforce.web_server

# Frontend (Node 18+)
cd FindMyForce-Web
npm install
npm run dev
```

**Dashboard:** http://localhost:5173  
**API:** http://localhost:5000

> **Note:** Model weights and training data are not included due to size. Place `signal_classifier.keras` in `models/` and `training_data.hdf5` in `dataset/`.

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Receiver API   │────▶│  Classification  │────▶│  Triangulation  │
│  (Flask, :5000) │     │  (RF + CNN)      │     │  (TDOA / RSSI)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              Common Operating Picture (React + Leaflet)         │
│         2D Map │ 3D Globe │ Track Inspector │ Live Stats        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
findmyforce-submission/
├── FindMyForce-API/
│   ├── findmyforce/
│   │   ├── classification/   # Feature extraction, RF classifier
│   │   ├── geolocate/        # TDOA, RSSI, coordinate conversion
│   │   ├── grouping/         # Signal association & clustering
│   │   ├── pipeline/         # Observation processing pipeline
│   │   └── web_server.py     # Flask API server
│   ├── config/               # Receiver positions, pathloss models
│   ├── models/               # Trained weights (.keras)
│   └── dataset/              # Training & evaluation data
│
├── FindMyForce-Web/
│   └── src/
│       ├── App.jsx           # Main layout, state management
│       ├── MapView.jsx       # Leaflet 2D tactical map
│       ├── Globe.jsx         # Three.js 3D globe
│       ├── Sidebar.jsx       # Track list with filters
│       ├── Inspector.jsx     # Detailed track analysis
│       └── data.js           # Mock data, receiver positions
│
├── run.sh / run.bat          # Launch both services
└── README.md
```

---

## API Reference

### Submit Observation

```python
import requests

API_URL = "https://findmyforce.online"
API_KEY = "your-api-key"

requests.post(f"{API_URL}/api/submit", json={
    "iq_data": [...],       # 256-element IQ vector
    "receiver_id": "RX-01",
    "timestamp": 1234567890
}, headers={"X-API-Key": API_KEY})
```

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tracks` | GET | Get all tracked emitters |
| `/config/receivers` | GET | Receiver station positions |
| `/eval/run` | POST | Run evaluation against ground truth |
| `/status` | GET | Server health & simulation state |

---

## Tech Stack

**Backend**
- Python 3.10, Poetry
- Scikit-learn (RandomForest, IsolationForest)
- TensorFlow/Keras (CNN classifier)
- Flask (REST API)
- SciPy (FFT, signal processing)

**Frontend**
- React 18, Vite
- Leaflet (2D maps)
- Three.js (3D globe)
- CSS variables, custom theming

---

## Background

This was my first hackathon, and it became one of the most valuable learning experiences I've had. Working with RF signal data and building ML classifiers from scratch sparked a genuine interest in machine learning that I've continued to pursue since.

The event brought together teams from BCIT, UBC, and SFU to tackle real defence technology challenges. Over an intense few days, we went from raw IQ samples to a working prototype that could detect and classify emitters in real-time.

---

## License

MIT — built for learning and experimentation.

---

**Acknowledgements:** UBC RedTeam Hackathon Series, Bovara Labs mentors, and the BCIT Computing community.
