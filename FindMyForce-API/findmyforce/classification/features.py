import numpy as np


def iq_to_complex(iq_snapshot):
    """Convert [I0..I127, Q0..Q127] format to 128 complex samples."""
    iq = np.array(iq_snapshot)
    i_data = iq[:128]
    q_data = iq[128:]
    return i_data + 1j * q_data


def extract_features(iq_snapshot):
    """Extract spectral features from a 256-length IQ snapshot ([0..127]=I, [128..255]=Q)."""
    cplx = iq_to_complex(iq_snapshot)
    fft = np.fft.fft(cplx)
    mag = np.abs(fft)
    psd = mag ** 2

    total_power = np.sum(psd)
    peak_idx = np.argmax(psd)
    peak_power = psd[peak_idx]
    peak_ratio = peak_power / (total_power + 1e-12)

    # Bandwidth: fraction of bins above 10% of peak
    threshold = 0.1 * peak_power
    bw_bins = np.sum(psd > threshold)
    bw_ratio = bw_bins / len(psd)

    # Spectral flatness (Wiener entropy)
    log_psd = np.log(psd + 1e-20)
    geo_mean = np.exp(np.mean(log_psd))
    arith_mean = np.mean(psd)
    flatness = geo_mean / (arith_mean + 1e-12)

    # Kurtosis of magnitude spectrum
    mu = np.mean(mag)
    std = np.std(mag) + 1e-12
    kurtosis = np.mean(((mag - mu) / std) ** 4)

    # Spectral rolloff (95% energy)
    cumsum = np.cumsum(psd)
    rolloff = np.searchsorted(cumsum, 0.95 * total_power) / len(psd)

    return {
        "peak_ratio": peak_ratio,
        "bw_ratio": bw_ratio,
        "flatness": flatness,
        "kurtosis": kurtosis,
        "rolloff": rolloff,
        "peak_idx": peak_idx,
    }


def extract_feature_vector(iq_snapshot):
    """Return features as a numpy array (for ML input)."""
    f = extract_features(iq_snapshot)
    return np.array([
        f["peak_ratio"],
        f["bw_ratio"],
        f["flatness"],
        f["kurtosis"],
        f["rolloff"],
        f["peak_idx"] / 128.0,  # normalize bin index (128 complex bins)
    ], dtype=np.float32)
