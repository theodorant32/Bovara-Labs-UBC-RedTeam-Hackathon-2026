"""
Test script for verifying observation processing and classification.

Usage:
    python test/test_obsrv.py                  # Test with cached observations
    python test/test_obsrv.py --fetch          # Fetch fresh observations
    python test/test_obsrv.py --plot           # Plot IQ spectra
    python test/test_obsrv.py --classify       # Classify cached observations
"""

import numpy as np
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from findmyforce.util.api_server import get_observations
from findmyforce.classification.features import extract_features, iq_to_complex
from findmyforce.classification.ml_classifier import classify_signal

CACHE_PATH = os.path.join(os.path.dirname(__file__), "test_obsrv.json")


def fetch_and_cache():
    """Fetch observations from server and cache locally."""
    print("Fetching observations from server...")
    data = get_observations(limit=50)
    with open(CACHE_PATH, "w") as f:
        json.dump(data, f)
    print(f"Cached {len(data.get('observations', []))} observations to {CACHE_PATH}")
    return data


def load_cached():
    """Load cached observations."""
    if not os.path.exists(CACHE_PATH):
        return fetch_and_cache()
    with open(CACHE_PATH, "r") as f:
        return json.load(f)


def test_classify():
    """Classify all cached observations and print results."""
    data = load_cached()
    observations = data["observations"]
    print(f"\nClassifying {len(observations)} observations:\n")
    print(f"{'Obs ID':<12} {'RX':<6} {'RSSI':>8} {'SNR':>8} {'Label':<22} {'Conf':>6}")
    print("-" * 70)

    for obs in observations:
        label, conf = classify_signal(obs["iq_snapshot"], obs.get("snr_estimate_db"))
        print(f"{obs['observation_id'][:10]}  {obs['receiver_id']:<6} "
              f"{obs['rssi_dbm']:>8.1f} {obs.get('snr_estimate_db', 0):>8.1f} "
              f"{label:<22} {conf:>6.3f}")


def test_features():
    """Print feature statistics for cached observations."""
    data = load_cached()
    observations = data["observations"]
    print(f"\nFeatures for {len(observations)} observations:\n")
    print(f"{'Obs ID':<12} {'peak_ratio':>12} {'bw_ratio':>12} {'flatness':>12} "
          f"{'kurtosis':>12} {'rolloff':>12}")
    print("-" * 74)

    for obs in observations[:20]:
        f = extract_features(obs["iq_snapshot"])
        print(f"{obs['observation_id'][:10]}  "
              f"{f['peak_ratio']:>12.4f} {f['bw_ratio']:>12.4f} "
              f"{f['flatness']:>12.4f} {f['kurtosis']:>12.4f} "
              f"{f['rolloff']:>12.4f}")


def test_plot():
    """Plot IQ spectra of first few observations."""
    import matplotlib.pyplot as plt

    data = load_cached()
    observations = data["observations"]

    fig, axes = plt.subplots(3, 3, figsize=(14, 10))
    axes = axes.flatten()

    for i, obs in enumerate(observations[:9]):
        cplx = iq_to_complex(obs["iq_snapshot"])
        fft = np.fft.fft(cplx)
        psd = np.abs(fft) ** 2

        label, conf = classify_signal(obs["iq_snapshot"])

        ax = axes[i]
        ax.plot(psd)
        ax.set_title(f"{obs['receiver_id']} | {label} ({conf:.2f})")
        ax.set_xlabel("Freq bin")
        ax.set_ylabel("PSD")

    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), "spectra.png"), dpi=100)
    plt.show()
    print("Saved to test/spectra.png")


if __name__ == "__main__":
    if "--fetch" in sys.argv:
        fetch_and_cache()
    elif "--plot" in sys.argv:
        test_plot()
    elif "--classify" in sys.argv:
        test_classify()
    elif "--features" in sys.argv:
        test_features()
    else:
        test_features()
        test_classify()
