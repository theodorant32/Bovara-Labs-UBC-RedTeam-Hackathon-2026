import os
import time
import json
import threading
import requests

# Load API key from environment or .env file
def _load_api_key():
    key = os.environ.get("FINDMYFORCE_API_KEY", "")
    if not key:
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("FINDMYFORCE_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        break
    return key

API_KEY = _load_api_key()
BASE = "https://findmyforce.online"

# Endpoints
HEALTH = "health"
FEED_STREAM = "feed/stream"
FEED_OBSRV = "feed/observations"
TEAM_SCORE = "scores/me"
RECV_CONF = "config/receivers"
RECV_PATHLOSS = "config/pathloss"
SUBM_CLASSFY = "submissions/classify"
SUBM_BATCH = "submissions/batch"
EVAL_OBSRV = "evaluate/observations"
EVAL_SUBMIT = "evaluate/submit"

# Rate limiting with per-endpoint tracking
_lock = threading.Lock()
_endpoint_times = {}
_default_interval_s = 5.0
_endpoint_intervals = {
    FEED_STREAM: 2.0,
    SUBM_BATCH: 2.0,
    SUBM_CLASSFY: 2.0,
    EVAL_SUBMIT: 2.0,
    EVAL_OBSRV: 2.0,
}

# Rate limit cooldown state
_rate_limited_until = 0.0
_COOLDOWN_SECONDS = 60.0


def is_rate_limited():
    """Check if we are currently in a rate-limit cooldown period."""
    return time.time() < _rate_limited_until


def cooldown_remaining():
    """Seconds remaining in cooldown, or 0 if not rate-limited."""
    return max(0.0, _rate_limited_until - time.time())


def _trigger_cooldown():
    """Activate a 60-second cooldown after detecting a rate limit."""
    global _rate_limited_until
    _rate_limited_until = time.time() + _COOLDOWN_SECONDS
    print(f"\n  *** RATE LIMITED — pausing submissions for {_COOLDOWN_SECONDS:.0f}s "
          f"(until {time.strftime('%H:%M:%S', time.localtime(_rate_limited_until))}) ***\n")


def _check_rate_limit_response(resp_json):
    """Check if the server response indicates a rate limit. Returns True if rate-limited."""
    if isinstance(resp_json, dict):
        detail = resp_json.get("detail", "")
        if "rate limit" in str(detail).lower():
            _trigger_cooldown()
            return True
    return False


def _rate_limit(endpoint=None):
    """Sleep if needed to enforce minimum interval between API calls."""
    with _lock:
        interval = _endpoint_intervals.get(endpoint, _default_interval_s)
        if interval <= 0:
            return

        key = endpoint or "__global__"
        now = time.time()
        last = _endpoint_times.get(key, 0.0)
        elapsed = now - last
        if elapsed < interval:
            time.sleep(interval - elapsed)
        _endpoint_times[key] = time.time()


def http_get(endpoint, **kwargs):
    _rate_limit(endpoint)
    resp = requests.get(
        f"{BASE}/{endpoint}",
        headers={"X-API-Key": API_KEY},
        **kwargs,
    )
    if resp.status_code == 429:
        _trigger_cooldown()
        return {"detail": "Rate limit exceeded"}
    result = resp.json()
    _check_rate_limit_response(result)
    return result


def http_post(endpoint, payload):
    _rate_limit(endpoint)
    resp = requests.post(
        f"{BASE}/{endpoint}",
        headers={"X-API-Key": API_KEY},
        json=payload,
    )
    if resp.status_code == 429:
        _trigger_cooldown()
        return {"detail": "Rate limit exceeded", "accepted_count": 0, "rejected_count": 0}
    result = resp.json()
    _check_rate_limit_response(result)
    return result


def get_status():
    return http_get(HEALTH)


def get_observations(since=None, limit=50, receiver_id=None):
    params = {"limit": limit}
    if since:
        params["since"] = since
    if receiver_id:
        params["receiver_id"] = receiver_id
    _rate_limit(FEED_OBSRV)
    resp = requests.get(
        f"{BASE}/{FEED_OBSRV}",
        headers={"X-API-Key": API_KEY},
        params=params,
    )
    if resp.status_code == 429:
        _trigger_cooldown()
        return {"observations": []}
    result = resp.json()
    _check_rate_limit_response(result)
    return result


def get_scores():
    return http_get(TEAM_SCORE)


def get_eval_observations():
    """Fetch evaluation observations (only available when evaluation_open=true)."""
    return http_get(EVAL_OBSRV)


def submit_eval(submissions):
    """Submit evaluation results. Returns score breakdown."""
    return http_post(EVAL_SUBMIT, {"submissions": submissions})


def stream_observations():
    """
    Connect to the SSE stream and yield observation dicts as they arrive.

    Event types:
      - 'observation': contains an observation JSON object
      - 'keepalive': empty, sent every 30s
    """
    resp = requests.get(
        f"{BASE}/{FEED_STREAM}",
        headers={"X-API-Key": API_KEY},
        stream=True,
    )
    resp.raise_for_status()

    event_type = None
    data_lines = []

    for line in resp.iter_lines(decode_unicode=True):
        if line is None:
            continue

        if line == "":
            if event_type == "observation" and data_lines:
                raw = "\n".join(data_lines)
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError:
                    pass
            event_type = None
            data_lines = []
            continue

        if line.startswith("event:"):
            event_type = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].strip())
