import numpy as np
from scipy.optimize import least_squares

from findmyforce.util.configs import load_receivers
from findmyforce.geolocate.coordinates import latlon_to_meters, meters_to_latlon

SPEED_OF_LIGHT = 299_792_458.0  # m/s


def locate_tdoa(measurements):
    """
    Estimate transmitter position from TDoA measurements via multilateration.

    Parameters
    ----------
    measurements : list[dict]
        Each dict has ``receiver_id`` (str) and ``toa_ns`` (float).
        At least 3 measurements are required.

    Returns
    -------
    dict with ``latitude``, ``longitude``, ``method``.
    """
    cfg = load_receivers()
    receivers = {r["receiver_id"]: (r["latitude"], r["longitude"])
                 for r in cfg["receivers"]}

    if len(measurements) < 3:
        raise ValueError("TDoA multilateration requires at least 3 receivers")

    measurements = sorted(measurements, key=lambda m: m["toa_ns"])

    ref = measurements[0]
    ref_rid = ref["receiver_id"]
    ref_toa = ref["toa_ns"]
    ref_latlon = receivers[ref_rid]

    lats = [receivers[m["receiver_id"]][0] for m in measurements]
    lons = [receivers[m["receiver_id"]][1] for m in measurements]
    ref_lat = np.mean(lats)
    ref_lon = np.mean(lons)

    rx_ref = np.array(latlon_to_meters(ref_latlon[0], ref_latlon[1],
                                       ref_lat, ref_lon))

    rx_xy = []
    delta_d = []
    for m in measurements[1:]:
        rid = m["receiver_id"]
        lat, lon = receivers[rid]
        rx_xy.append(latlon_to_meters(lat, lon, ref_lat, ref_lon))
        dt_s = (m["toa_ns"] - ref_toa) * 1e-9
        delta_d.append(SPEED_OF_LIGHT * dt_s)

    rx_xy = np.array(rx_xy)
    delta_d = np.array(delta_d)

    all_xy = np.vstack([rx_ref, rx_xy])
    x0 = np.mean(all_xy, axis=0)

    def residuals(pos):
        d_to_others = np.sqrt(np.sum((rx_xy - pos) ** 2, axis=1))
        d_to_ref = np.linalg.norm(pos - rx_ref)
        return (d_to_others - d_to_ref) - delta_d

    result = least_squares(residuals, x0)
    est_x, est_y = result.x

    est_lat, est_lon = meters_to_latlon(est_x, est_y, ref_lat, ref_lon)
    return {"latitude": est_lat, "longitude": est_lon, "method": "tdoa"}
