import numpy as np
from scipy.optimize import least_squares, minimize

from findmyforce.util.configs import load_pathloss, load_receivers
from findmyforce.geolocate.coordinates import latlon_to_meters, meters_to_latlon


def rssi_to_distance(rssi_dbm):
    """
    Estimate distance from RSSI using the log-distance path loss model.

    d = d0 * 10^((RSSI_ref - RSSI) / (10 * n))
    """
    pathloss = load_pathloss()
    rssi_ref = pathloss["rssi_ref_dbm"]
    d_ref = pathloss["d_ref_m"]
    n = pathloss["path_loss_exponent"]

    exponent = (rssi_ref - rssi_dbm) / (10.0 * n)
    distance_m = d_ref * (10.0 ** exponent)
    return distance_m


def trilaterate(receiver_positions, distances, weights=None):
    """
    Estimate emitter position from multiple receiver distances.

    receiver_positions: list of (x, y) in metres
    distances:          list of estimated distances in metres
    weights:            optional per-observation weights (higher = more trusted)

    Returns (x, y) in metres.
    """
    positions = np.array(receiver_positions)
    dists = np.array(distances)

    if weights is None:
        weights = np.ones(len(dists))
    weights = np.array(weights)

    x0 = np.average(positions[:, 0], weights=weights)
    y0 = np.average(positions[:, 1], weights=weights)

    def cost(p):
        dx = positions[:, 0] - p[0]
        dy = positions[:, 1] - p[1]
        predicted = np.sqrt(dx**2 + dy**2)
        residuals = (predicted - dists) * weights
        return np.sum(residuals**2)

    result = minimize(cost, [x0, y0], method="Nelder-Mead")
    return result.x


def locate_rssi(measurements):
    """
    Estimate transmitter position from RSSI measurements via trilateration.

    Parameters
    ----------
    measurements : list[dict]
        Each dict has ``receiver_id`` (str) and ``rssi_dbm`` (float).
        At least 3 measurements are required.

    Returns
    -------
    dict with ``latitude``, ``longitude``, ``method``.
    """
    cfg = load_receivers()
    receivers = {r["receiver_id"]: (r["latitude"], r["longitude"])
                 for r in cfg["receivers"]}

    rx_coords = []
    distances = []
    lats, lons = [], []
    for m in measurements:
        rid = m["receiver_id"]
        lat, lon = receivers[rid]
        lats.append(lat)
        lons.append(lon)
        rx_coords.append((lat, lon))
        distances.append(rssi_to_distance(m["rssi_dbm"]))

    if len(rx_coords) < 3:
        raise ValueError("RSSI trilateration requires at least 3 receivers")

    ref_lat = np.mean(lats)
    ref_lon = np.mean(lons)

    rx_xy = np.array([latlon_to_meters(lat, lon, ref_lat, ref_lon)
                      for lat, lon in rx_coords])
    d = np.array(distances)

    weights = 1.0 / (d + 1e-6)
    x0 = np.average(rx_xy, axis=0, weights=weights)

    def residuals(pos):
        return np.sqrt(np.sum((rx_xy - pos) ** 2, axis=1)) - d

    result = least_squares(residuals, x0)
    est_x, est_y = result.x

    est_lat, est_lon = meters_to_latlon(est_x, est_y, ref_lat, ref_lon)
    return {"latitude": est_lat, "longitude": est_lon, "method": "rssi"}
