"""
Local web server that bridges the FindMyForce backend API to the web frontend.

Exposes REST endpoints at http://localhost:5000 for the React COP dashboard.
"""

import os
import sys
import json
import time
import threading
from collections import Counter
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Ensure package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from findmyforce.util.api_server import (
    get_observations, get_status, get_scores,
    get_eval_observations, submit_eval,
    stream_observations, is_rate_limited,
)
from findmyforce.pipeline.processor import (
    process_observations, classify_batch_fast, classify_single,
)

# In-memory track state
_tracks_lock = threading.Lock()
_tracks = []
_eval_result = None
_last_fetch = 0

# Classification to frontend class mapping
_CLS_MAP = {
    "Radar-Altimeter": "friendly",
    "Satcom": "friendly",
    "short-range": "friendly",
    "AM radio": "civilian",
    "Airborne-detection": "hostile",
    "Airborne-range": "hostile",
    "Air-Ground-MTI": "hostile",
    "EW-Jammer": "hostile",
}

_MOD_MAP = {
    "Radar-Altimeter": "FMCW",
    "Satcom": "BPSK",
    "short-range": "ASK",
    "AM radio": "AM-DSB",
    "Airborne-detection": "Pulsed",
    "Airborne-range": "Pulsed",
    "Air-Ground-MTI": "Pulsed",
    "EW-Jammer": "Jamming",
}

_track_counter = 0
_obs_to_track = {}


def _submission_to_track(sub, obs=None):
    """Convert a pipeline submission dict to a frontend track dict."""
    global _track_counter

    obs_id = sub["observation_id"]
    if obs_id in _obs_to_track:
        trk_id = _obs_to_track[obs_id]
    else:
        _track_counter += 1
        trk_id = f"TRK-{_track_counter:03d}"
        _obs_to_track[obs_id] = trk_id

    label = sub["classification_label"]
    cls = _CLS_MAP.get(label, "unknown")

    return {
        "id": trk_id,
        "obs_id": obs_id,
        "cls": cls,
        "type": label,
        "mod": _MOD_MAP.get(label, "UNKNOWN"),
        "lat": sub.get("estimated_latitude", 49.263),
        "lon": sub.get("estimated_longitude", -123.248),
        "rssi": obs["rssi_dbm"] if obs else -70,
        "snr": round(obs["snr_estimate_db"], 1) if obs and obs.get("snr_estimate_db") else 0,
        "conf": sub.get("confidence", 0.5),
        "obs": 1,
        "cep": 150,
        "stale": False,
    }


def fetch_and_process():
    """Fetch latest observations, classify, geolocate, update track state."""
    global _tracks, _last_fetch
    try:
        data = get_observations(limit=50)
        observations = data.get("observations", [])
        if not observations:
            return

        submissions = process_observations(observations)
        obs_lookup = {o["observation_id"]: o for o in observations}

        new_tracks = []
        for sub in submissions:
            obs = obs_lookup.get(sub["observation_id"])
            new_tracks.append(_submission_to_track(sub, obs))

        # Deduplicate by keeping latest per track type + approximate location
        with _tracks_lock:
            _tracks = new_tracks
            _last_fetch = time.time()

        print(f"  Updated {len(new_tracks)} tracks")
    except Exception as e:
        print(f"  Error fetching: {e}")


def run_evaluation():
    """Run evaluation and return results."""
    global _eval_result
    try:
        status = get_status()
        print(f"Server: {status.get('simulation_state', '?')}  "
              f"eval_open: {status.get('evaluation_open', False)}")

        if not status.get("evaluation_open", False):
            return {"error": "Evaluation is not open yet"}

        data = get_eval_observations()
        eval_obs = data.get("observations", [])
        if not eval_obs:
            return {"error": "No evaluation observations available"}

        print(f"  {len(eval_obs)} evaluation observations")
        submissions = classify_batch_fast(eval_obs)
        print(f"  {len(submissions)} submissions prepared")

        labels = Counter(s["classification_label"] for s in submissions)
        print(f"  Labels: {dict(labels)}")

        result = submit_eval(submissions)
        _eval_result = result

        # Also update tracks with eval data
        obs_lookup = {o["observation_id"]: o for o in eval_obs}
        new_tracks = []
        for sub in submissions:
            obs = obs_lookup.get(sub["observation_id"])
            new_tracks.append(_submission_to_track(sub, obs))

        with _tracks_lock:
            _tracks.extend(new_tracks)

        return result
    except Exception as e:
        return {"error": str(e)}


class CORSHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler with CORS for the frontend."""

    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json_response(self, data, status=200):
        self._set_headers(status)
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/tracks":
            with _tracks_lock:
                self._json_response(_tracks)

        elif path == "/status":
            try:
                status = get_status()
                status["track_count"] = len(_tracks)
                status["last_fetch"] = _last_fetch
                self._json_response(status)
            except Exception as e:
                self._json_response({"error": str(e)}, 500)

        elif path == "/scores":
            try:
                self._json_response(get_scores())
            except Exception as e:
                self._json_response({"error": str(e)}, 500)

        elif path == "/eval/result":
            if _eval_result:
                self._json_response(_eval_result)
            else:
                self._json_response({"error": "No evaluation run yet"}, 404)

        elif path == "/refresh":
            threading.Thread(target=fetch_and_process, daemon=True).start()
            self._json_response({"status": "refreshing"})

        else:
            self._json_response({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/eval/run":
            result = run_evaluation()
            self._json_response(result)
        else:
            self._json_response({"error": "Not found"}, 404)

    def log_message(self, format, *args):
        # Quieter logging
        if "404" in str(args):
            return
        print(f"  [{time.strftime('%H:%M:%S')}] {args[0]}")


def polling_loop(interval=10):
    """Background thread that periodically fetches and processes observations."""
    while True:
        fetch_and_process()
        time.sleep(interval)


def main():
    port = int(os.environ.get("PORT", 5000))

    print(f"FindMyForce Bridge Server starting on http://localhost:{port}")
    print(f"  Endpoints:")
    print(f"    GET  /tracks      - Current tracks for COP")
    print(f"    GET  /status      - Server status")
    print(f"    GET  /scores      - Team scores")
    print(f"    GET  /refresh     - Trigger manual refresh")
    print(f"    POST /eval/run    - Run evaluation")
    print(f"    GET  /eval/result - Last evaluation result")
    print()

    # Initial fetch
    print("Initial data fetch...")
    fetch_and_process()

    # Start background polling
    poller = threading.Thread(target=polling_loop, args=(15,), daemon=True)
    poller.start()
    print("Background polling started (every 15s)")

    server = HTTPServer(("0.0.0.0", port), CORSHandler)
    print(f"Server ready on port {port}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
