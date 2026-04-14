import numpy as np


def latlon_to_meters(lat, lon, ref_lat, ref_lon):
    """Convert lat/lon to local metre offsets from a reference point."""
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * np.cos(np.radians(ref_lat))
    x = (lon - ref_lon) * m_per_deg_lon
    y = (lat - ref_lat) * m_per_deg_lat
    return x, y


def meters_to_latlon(x, y, ref_lat, ref_lon):
    """Convert local metre offsets back to lat/lon."""
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * np.cos(np.radians(ref_lat))
    lon = ref_lon + x / m_per_deg_lon
    lat = ref_lat + y / m_per_deg_lat
    return lat, lon
