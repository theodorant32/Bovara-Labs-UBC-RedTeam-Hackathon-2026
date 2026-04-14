import numpy as np
from collections import defaultdict

from findmyforce.classification.features import iq_to_complex


def spectral_fingerprint(iq_snapshot):
    """Compute normalized PSD from IQ samples ([0..127]=I, [128..255]=Q)."""
    cplx = iq_to_complex(iq_snapshot)
    fft = np.fft.fft(cplx)
    psd = np.abs(fft) ** 2
    psd = psd / (np.sum(psd) + 1e-12)
    return psd


def doppler_tolerant_similarity(psd_a, psd_b):
    """
    Max normalized cross-correlation across frequency shifts.

    Robust to Doppler shift from moving transmitters — finds the
    frequency offset that maximizes alignment between two PSDs.
    """
    corr = np.correlate(psd_a, psd_b, mode="full")
    norm = np.linalg.norm(psd_a) * np.linalg.norm(psd_b) + 1e-12
    return np.max(corr) / norm


def group_observations(observations):
    """
    Group observations that likely come from the same emitter.

    Uses Doppler-tolerant cross-correlation of spectral fingerprints.
    """
    obsrv_count = len(observations)
    obsrv_psd = [spectral_fingerprint(obs["iq_snapshot"]) for obs in observations]

    # Build similarity matrix using cross-correlation
    similarity = np.zeros((obsrv_count, obsrv_count))
    for i in range(obsrv_count):
        similarity[i, i] = 1.0
        for j in range(i + 1, obsrv_count):
            sim = doppler_tolerant_similarity(obsrv_psd[i], obsrv_psd[j])
            similarity[i, j] = sim
            similarity[j, i] = sim

    # Greedy clustering with similarity threshold
    THRESHOLD = 0.65
    assigned = [-1] * obsrv_count
    group_id = 0

    for i in range(obsrv_count):
        if assigned[i] >= 0:
            continue
        assigned[i] = group_id
        for j in range(i + 1, obsrv_count):
            if assigned[j] >= 0:
                continue
            # Same receiver can't appear twice in one group
            group_rxs = {
                observations[k]["receiver_id"]
                for k in range(obsrv_count)
                if assigned[k] == group_id
            }
            if observations[j]["receiver_id"] in group_rxs:
                continue
            if similarity[i, j] > THRESHOLD:
                assigned[j] = group_id
        group_id += 1

    groups = defaultdict(list)
    for idx, gid in enumerate(assigned):
        groups[gid].append(observations[idx])
    return dict(groups)
