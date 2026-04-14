import os
import json

import numpy as np

from findmyforce.util.api_server import http_get, RECV_CONF, RECV_PATHLOSS

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "config")


def load_pathloss(force_reload=False):
    path = os.path.join(CONFIG_DIR, "pathloss.json")
    if not os.path.exists(path) or force_reload:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = http_get(RECV_PATHLOSS)
        with open(path, "w") as f:
            json.dump(data, f)
    with open(path, "r") as f:
        return json.load(f)


def load_receivers(force_reload=False):
    path = os.path.join(CONFIG_DIR, "receivers.json")
    if not os.path.exists(path) or force_reload:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = http_get(RECV_CONF)
        # Add reference coordinates (centroid of all receivers)
        ref_lat = np.mean([r["latitude"] for r in data["receivers"]])
        ref_lon = np.mean([r["longitude"] for r in data["receivers"]])
        data["reference_coordinates"] = {
            "latitude": ref_lat,
            "longitude": ref_lon,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    with open(path, "r") as f:
        return json.load(f)
