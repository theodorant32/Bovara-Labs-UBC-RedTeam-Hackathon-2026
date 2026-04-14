import numpy as np

from findmyforce.util.api_server import http_post, SUBM_BATCH, SUBM_CLASSFY
from findmyforce.util.configs import load_receivers
from findmyforce.geolocate.coordinates import latlon_to_meters, meters_to_latlon
from findmyforce.geolocate.rssi import rssi_to_distance, trilaterate
from findmyforce.grouping.signal_grouping import group_observations
from findmyforce.classification.ml_classifier import classify_signal, _iq_to_2ch, _get_model, ALL_LABELS, ML_LABELS, _classify_hostile

# Cached receiver data
_receivers = None
_rx_positions = None
_ref_lat = None
_ref_lon = None


def _ensure_receivers():
    """Load and cache receiver positions (called once)."""
    global _receivers, _rx_positions, _ref_lat, _ref_lon
    if _receivers is not None:
        return

    cfg = load_receivers()
    _receivers = {r["receiver_id"]: r for r in cfg["receivers"]}
    _ref_lat = np.mean([r["latitude"] for r in _receivers.values()])
    _ref_lon = np.mean([r["longitude"] for r in _receivers.values()])

    _rx_positions = {}
    for rx_id, rx in _receivers.items():
        x, y = latlon_to_meters(rx["latitude"], rx["longitude"], _ref_lat, _ref_lon)
        _rx_positions[rx_id] = (x, y)


def classify_single(obs):
    """Classify a single observation (fast path — no grouping)."""
    label, confidence = classify_signal(obs["iq_snapshot"], obs.get("snr_estimate_db"))

    _ensure_receivers()
    rx_id = obs["receiver_id"]
    if rx_id in _receivers:
        rx = _receivers[rx_id]
        est_lat = rx["latitude"]
        est_lon = rx["longitude"]
    else:
        est_lat = _ref_lat
        est_lon = _ref_lon

    return {
        "observation_id": obs["observation_id"],
        "classification_label": label,
        "confidence": round(confidence, 3),
        "estimated_latitude": round(est_lat, 6),
        "estimated_longitude": round(est_lon, 6),
    }


def classify_batch_fast(observations):
    """
    Batch-classify observations using a single model.predict() call.

    Skips grouping for speed — classifies each observation independently
    and uses receiver position as location estimate.
    """
    _ensure_receivers()
    model = _get_model()

    submissions = []

    if model is not None and observations:
        # Batch predict all IQ snapshots at once
        iq_batch = np.array([_iq_to_2ch(o["iq_snapshot"]) for o in observations])
        probs_batch = model.predict(iq_batch, verbose=0)

        num_classes = probs_batch.shape[1]
        labels_list = ALL_LABELS if num_classes == len(ALL_LABELS) else ML_LABELS
        confidence_threshold = 0.5 if num_classes == len(ALL_LABELS) else 0.6

        for i, obs in enumerate(observations):
            probs = probs_batch[i]
            best_idx = int(np.argmax(probs))
            confidence = float(probs[best_idx])

            if confidence >= confidence_threshold:
                label = labels_list[best_idx]
            else:
                label, confidence = _classify_hostile(obs["iq_snapshot"])

            rx_id = obs["receiver_id"]
            if rx_id in _receivers:
                rx = _receivers[rx_id]
                est_lat, est_lon = rx["latitude"], rx["longitude"]
            else:
                est_lat, est_lon = _ref_lat, _ref_lon

            submissions.append({
                "observation_id": obs["observation_id"],
                "classification_label": label,
                "confidence": round(confidence, 3),
                "estimated_latitude": round(est_lat, 6),
                "estimated_longitude": round(est_lon, 6),
            })
    else:
        for obs in observations:
            submissions.append(classify_single(obs))

    return submissions


def process_observations(observations):
    """
    Full pipeline: group -> classify -> geolocate -> build submissions.

    Returns list of submission dicts ready for batch POST.
    """
    _ensure_receivers()

    groups = group_observations(observations)
    submissions = []

    for gid, group_obs in groups.items():
        best_obs = max(group_obs, key=lambda o: o["snr_estimate_db"])
        label, confidence = classify_signal(best_obs["iq_snapshot"], best_obs["snr_estimate_db"])

        rx_coords = []
        dists = []
        weights = []

        for obs in group_obs:
            rx_id = obs["receiver_id"]
            if rx_id not in _receivers:
                continue

            dist = rssi_to_distance(obs["rssi_dbm"])
            snr = obs["snr_estimate_db"]
            weight = max(0.1, (snr + 10.0) / 50.0)

            rx_coords.append(_rx_positions[rx_id])
            dists.append(dist)
            weights.append(weight)

        if len(rx_coords) >= 3:
            est_x, est_y = trilaterate(rx_coords, dists, weights)
        elif len(rx_coords) == 2:
            w = np.array(weights)
            w = w / w.sum()
            coords = np.array(rx_coords)
            d = np.array(dists)
            direction = coords[1] - coords[0]
            dir_norm = np.linalg.norm(direction) + 1e-12
            direction = direction / dir_norm
            p1 = coords[0] + direction * d[0]
            p2 = coords[1] - direction * d[1]
            est_x = w[0] * p1[0] + w[1] * p2[0]
            est_y = w[0] * p1[1] + w[1] * p2[1]
        elif len(rx_coords) == 1:
            est_x, est_y = rx_coords[0]
        else:
            continue

        est_lat, est_lon = meters_to_latlon(est_x, est_y, _ref_lat, _ref_lon)

        for obs in group_obs:
            submissions.append({
                "observation_id": obs["observation_id"],
                "classification_label": label,
                "confidence": round(confidence, 3),
                "estimated_latitude": round(est_lat, 6),
                "estimated_longitude": round(est_lon, 6),
            })

    return submissions


def submit_batch(submissions):
    """POST batch submissions to the API."""
    return http_post(SUBM_BATCH, {"submissions": submissions})


def submit_single(submission):
    """POST a single classification to the API."""
    return http_post(SUBM_CLASSFY, submission)
