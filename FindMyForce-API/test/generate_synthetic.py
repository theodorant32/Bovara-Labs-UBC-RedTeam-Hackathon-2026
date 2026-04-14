"""
Generate synthetic IQ datasets for hostile and civilian signal types
that are NOT in the training data.

Signal types and their modulation characteristics:
  Hostile:
    - Airborne-detection: Pulsed surveillance radar (wide-bandwidth pulses)
    - Airborne-range:     Pulsed range-finding radar (narrow pulses, high PRF)
    - Air-Ground-MTI:     Pulsed MTI radar (wideband, Doppler processing)
    - EW-Jammer:          Broadband noise jamming
  Civilian:
    - AM radio:           AM-DSB (strong carrier + symmetric sidebands)

Each sample is 128 complex IQ points stored as 256 floats [I0..I127, Q0..Q127].

Augmentations applied:
  - RSSI-based amplitude scaling (simulate different distances/power levels)
  - Moving target Doppler shift (time-varying frequency offset)
  - Multipath fading (Rayleigh/Rician channel model)
  - Phase noise and timing jitter
  - Random frequency offset (oscillator drift)
"""

import os
import sys
import numpy as np
import h5py

N_SAMPLES = 128  # IQ samples per snapshot (matches server format)
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset")


# ---------------------------------------------------------------------------
# Noise and augmentation utilities
# ---------------------------------------------------------------------------

def add_noise(signal, snr_db):
    """Add AWGN noise to achieve a target SNR."""
    sig_power = np.mean(np.abs(signal) ** 2)
    if sig_power < 1e-20:
        return signal
    noise_power = sig_power / (10 ** (snr_db / 10))
    noise = np.sqrt(noise_power / 2) * (np.random.randn(len(signal)) + 1j * np.random.randn(len(signal)))
    return signal + noise


def apply_rssi_scaling(signal):
    """Simulate different received power levels (distance variation).
    Scales amplitude by a random factor corresponding to RSSI range -30 to -90 dBm."""
    # Random attenuation: 0 to 30 dB (linear scale 1.0 down to 0.03)
    atten_db = np.random.uniform(0, 30)
    scale = 10 ** (-atten_db / 20)
    return signal * scale


def apply_doppler_shift(signal, max_shift_bins=5.0):
    """Apply a time-varying Doppler frequency shift (moving target).
    Simulates acceleration by using a chirp-like phase ramp."""
    n = len(signal)
    t = np.arange(n) / n

    # Constant velocity component
    f_shift = np.random.uniform(-max_shift_bins, max_shift_bins) / n
    # Acceleration component (frequency changes over snapshot)
    f_accel = np.random.uniform(-2.0, 2.0) / n

    phase = 2 * np.pi * (f_shift * np.arange(n) + 0.5 * f_accel * np.arange(n) ** 2 / n)
    return signal * np.exp(1j * phase)


def apply_multipath(signal, num_paths=None):
    """Simulate multipath fading (Rician channel).
    Direct path + weaker delayed reflections."""
    if num_paths is None:
        num_paths = np.random.randint(1, 4)

    result = signal.copy()
    for _ in range(num_paths):
        # Random delay (fractional samples)
        delay = np.random.randint(1, 8)
        # Random attenuation (reflection is weaker)
        atten = np.random.uniform(0.1, 0.5)
        # Random phase shift
        phase = np.random.uniform(0, 2 * np.pi)

        delayed = np.roll(signal, delay) * atten * np.exp(1j * phase)
        result += delayed

    return result


def apply_phase_noise(signal, noise_std_rad=0.1):
    """Add random phase noise (oscillator imperfections)."""
    phase_noise = np.cumsum(np.random.randn(len(signal)) * noise_std_rad)
    return signal * np.exp(1j * phase_noise)


def apply_freq_offset(signal, max_offset_bins=3.0):
    """Apply a constant frequency offset (oscillator drift)."""
    n = len(signal)
    offset = np.random.uniform(-max_offset_bins, max_offset_bins) / n
    return signal * np.exp(1j * 2 * np.pi * offset * np.arange(n))


def apply_augmentations(signal, aug_prob=0.7):
    """Randomly apply a subset of augmentations to a signal."""
    if np.random.random() < aug_prob:
        signal = apply_rssi_scaling(signal)
    if np.random.random() < 0.5:
        signal = apply_doppler_shift(signal)
    if np.random.random() < 0.3:
        signal = apply_multipath(signal)
    if np.random.random() < 0.4:
        signal = apply_phase_noise(signal, noise_std_rad=np.random.uniform(0.02, 0.2))
    if np.random.random() < 0.4:
        signal = apply_freq_offset(signal)
    return signal


def to_iq_256(complex_signal):
    """Convert 128 complex samples to 256-float [I, Q] format."""
    return np.concatenate([complex_signal.real, complex_signal.imag]).astype(np.float32)


# ---------------------------------------------------------------------------
# Signal generators
# ---------------------------------------------------------------------------

def gen_pulsed_radar(n=N_SAMPLES, pulse_width_frac=0.15, prf_cycles=2.0,
                     carrier_freq_bin=20, bw_bins=8):
    """
    Generate pulsed radar signal.

    pulse_width_frac: fraction of the period that the pulse is ON
    prf_cycles: number of pulse repetitions in the snapshot
    carrier_freq_bin: center frequency (as FFT bin)
    bw_bins: bandwidth of the pulse (wider = shorter pulse in time)
    """
    t = np.arange(n) / n

    # Pulse envelope (rectangular pulses)
    period = 1.0 / prf_cycles
    envelope = np.zeros(n)
    for k in range(int(prf_cycles) + 1):
        start = k * period
        end = start + pulse_width_frac * period
        mask = (t >= start) & (t < end)
        envelope[mask] = 1.0

    # Add some rise/fall time to make it realistic
    from scipy.ndimage import gaussian_filter1d
    envelope = gaussian_filter1d(envelope, sigma=np.random.uniform(0.5, 2.0))

    # Carrier with some bandwidth (chirp within pulse)
    carrier_freq = carrier_freq_bin / n
    phase = 2 * np.pi * carrier_freq * np.arange(n)
    # Add slight frequency modulation for bandwidth
    chirp_rate = bw_bins / (n * pulse_width_frac / prf_cycles)
    phase += np.pi * chirp_rate * t ** 2

    signal = envelope * np.exp(1j * phase)
    return signal


def gen_airborne_detection(n=N_SAMPLES, snr_db=10):
    """Airborne surveillance radar: wide-bandwidth pulsed, moderate PRF."""
    carrier = np.random.randint(10, 55)
    pw = np.random.uniform(0.08, 0.18)
    prf = np.random.uniform(2.0, 4.0)
    bw = np.random.randint(8, 16)
    signal = gen_pulsed_radar(n, pulse_width_frac=pw, prf_cycles=prf,
                              carrier_freq_bin=carrier, bw_bins=bw)
    signal = apply_augmentations(signal)
    return add_noise(signal, snr_db)


def gen_airborne_range(n=N_SAMPLES, snr_db=10):
    """Airborne range-finding radar: narrow pulses, high PRF."""
    carrier = np.random.randint(15, 50)
    pw = np.random.uniform(0.04, 0.12)
    prf = np.random.uniform(4.0, 7.0)
    bw = np.random.randint(4, 10)
    signal = gen_pulsed_radar(n, pulse_width_frac=pw, prf_cycles=prf,
                              carrier_freq_bin=carrier, bw_bins=bw)
    signal = apply_augmentations(signal)
    return add_noise(signal, snr_db)


def gen_air_ground_mti(n=N_SAMPLES, snr_db=10):
    """Air-to-ground MTI radar: wideband pulsed with Doppler modulation."""
    carrier = np.random.randint(8, 58)
    pw = np.random.uniform(0.12, 0.25)
    prf = np.random.uniform(3.0, 6.0)
    bw = np.random.randint(10, 20)
    signal = gen_pulsed_radar(n, pulse_width_frac=pw, prf_cycles=prf,
                              carrier_freq_bin=carrier, bw_bins=bw)
    # Strong Doppler modulation (moving ground targets)
    t = np.arange(n) / n
    doppler_shift = np.random.uniform(1, 10)
    signal *= np.exp(1j * 2 * np.pi * doppler_shift * t)
    signal = apply_augmentations(signal)
    return add_noise(signal, snr_db)


def gen_ew_jammer(n=N_SAMPLES, snr_db=10):
    """EW jammer: broadband noise-like signal across wide bandwidth."""
    bw_fraction = np.random.uniform(0.4, 0.95)
    noise = np.random.randn(n) + 1j * np.random.randn(n)

    # Bandpass filter to shape the jamming bandwidth
    fft = np.fft.fft(noise)
    center = np.random.randint(n // 4, 3 * n // 4)
    bw = int(bw_fraction * n / 2)
    mask = np.zeros(n)
    low = max(0, center - bw)
    high = min(n, center + bw)
    mask[low:high] = 1.0
    fft *= mask
    signal = np.fft.ifft(fft)

    # Normalize
    signal = signal / (np.max(np.abs(signal)) + 1e-12)

    # Jammer-specific: sometimes pulse the jamming (sweep or burst)
    if np.random.random() < 0.3:
        t = np.arange(n) / n
        burst_freq = np.random.uniform(1, 5)
        envelope = 0.5 + 0.5 * np.cos(2 * np.pi * burst_freq * t)
        signal *= envelope

    signal = apply_augmentations(signal)
    return add_noise(signal, snr_db)


def gen_am_radio(n=N_SAMPLES, snr_db=10):
    """AM-DSB radio: strong carrier + symmetric sidebands from audio modulation."""
    t = np.arange(n) / n

    # Carrier frequency
    carrier_freq = np.random.randint(20, 55)
    carrier = np.exp(1j * 2 * np.pi * carrier_freq * t)

    # Audio modulation (sum of a few low-frequency tones)
    num_tones = np.random.randint(2, 6)
    audio = np.zeros(n)
    for _ in range(num_tones):
        freq = np.random.uniform(0.5, 8)  # low-frequency audio
        audio += np.random.uniform(0.05, 0.5) * np.cos(
            2 * np.pi * freq * t + np.random.uniform(0, 2 * np.pi))

    # AM modulation: (1 + m*audio) * carrier
    mod_depth = np.random.uniform(0.2, 0.9)
    signal = (1.0 + mod_depth * audio) * carrier

    signal = apply_augmentations(signal)
    return add_noise(signal, snr_db)


# ---------------------------------------------------------------------------
# Friendly signal generators (data augmentation for training set)
# ---------------------------------------------------------------------------

def gen_radar_altimeter(n=N_SAMPLES, snr_db=10):
    """Radar altimeter: FMCW-like continuous wave, narrow bandwidth."""
    t = np.arange(n) / n
    carrier = np.random.randint(30, 55)
    sweep_bw = np.random.uniform(2, 8)  # narrow sweep
    # Linear FM chirp
    phase = 2 * np.pi * (carrier * t + 0.5 * sweep_bw * t ** 2)
    signal = np.exp(1j * phase)
    signal = apply_augmentations(signal)
    return add_noise(signal, snr_db)


def gen_satcom(n=N_SAMPLES, snr_db=10):
    """Satcom: BPSK/QPSK digital modulation, moderate bandwidth."""
    t = np.arange(n) / n
    carrier = np.random.randint(25, 50)

    # QPSK: symbols at regular intervals
    sym_rate = np.random.randint(4, 16)  # symbols per snapshot
    symbols = np.random.choice([0, np.pi / 2, np.pi, 3 * np.pi / 2], size=sym_rate)
    # Map symbols to samples
    phase_mod = np.zeros(n)
    samples_per_sym = n // sym_rate
    for i, sym in enumerate(symbols):
        start = i * samples_per_sym
        end = min(n, (i + 1) * samples_per_sym)
        phase_mod[start:end] = sym

    phase = 2 * np.pi * carrier * t + phase_mod
    signal = np.exp(1j * phase)
    signal = apply_augmentations(signal)
    return add_noise(signal, snr_db)


def gen_short_range(n=N_SAMPLES, snr_db=10):
    """Short-range: ASK/OOK digital modulation, bursty."""
    t = np.arange(n) / n
    carrier = np.random.randint(15, 45)

    # OOK: on-off keying
    sym_rate = np.random.randint(4, 12)
    bits = np.random.choice([0.0, 1.0], size=sym_rate)
    envelope = np.zeros(n)
    samples_per_sym = n // sym_rate
    for i, bit in enumerate(bits):
        start = i * samples_per_sym
        end = min(n, (i + 1) * samples_per_sym)
        envelope[start:end] = bit

    # Smooth transitions
    from scipy.ndimage import gaussian_filter1d
    envelope = gaussian_filter1d(envelope, sigma=1.5)

    signal = envelope * np.exp(1j * 2 * np.pi * carrier * t)
    signal = apply_augmentations(signal)
    return add_noise(signal, snr_db)


# ---------------------------------------------------------------------------
# Dataset generation
# ---------------------------------------------------------------------------

GENERATORS = {
    "Airborne-detection": gen_airborne_detection,
    "Airborne-range": gen_airborne_range,
    "Air-Ground-MTI": gen_air_ground_mti,
    "EW-Jammer": gen_ew_jammer,
    "AM radio": gen_am_radio,
}

# Friendly augmentation generators
FRIENDLY_GENERATORS = {
    "Radar-Altimeter": gen_radar_altimeter,
    "Satcom": gen_satcom,
    "short-range": gen_short_range,
}

SNR_RANGE = list(range(-20, 20, 2))  # -20 to 18 dB, step 2


def generate_dataset(samples_per_class_per_snr=50, output_file=None,
                     include_friendly_aug=True, friendly_samples_per_snr=20):
    """Generate synthetic dataset for hostile/civilian + optional friendly augmentation."""
    if output_file is None:
        output_file = os.path.join(OUTPUT_DIR, "synthetic_hostile.hdf5")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    total = 0
    with h5py.File(output_file, "w") as f:
        # Hostile + civilian signals
        for label, gen_fn in GENERATORS.items():
            for snr in SNR_RANGE:
                for i in range(samples_per_class_per_snr):
                    signal = gen_fn(snr_db=snr)
                    iq_256 = to_iq_256(signal)

                    key = str(("synthetic", label, snr, i))
                    f.create_dataset(key, data=iq_256)
                    total += 1

            count = samples_per_class_per_snr * len(SNR_RANGE)
            print(f"  Generated {label}: {count} samples")

        # Friendly signal augmentations
        if include_friendly_aug:
            for label, gen_fn in FRIENDLY_GENERATORS.items():
                for snr in SNR_RANGE:
                    for i in range(friendly_samples_per_snr):
                        signal = gen_fn(snr_db=snr)
                        iq_256 = to_iq_256(signal)

                        key = str(("synthetic", label, snr, i))
                        f.create_dataset(key, data=iq_256)
                        total += 1

                count = friendly_samples_per_snr * len(SNR_RANGE)
                print(f"  Generated {label} (aug): {count} samples")

    print(f"\nTotal: {total} samples saved to {output_file}")
    return output_file


def verify_dataset(filepath=None):
    """Load and verify the synthetic dataset, print feature statistics."""
    if filepath is None:
        filepath = os.path.join(OUTPUT_DIR, "synthetic_hostile.hdf5")

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from findmyforce.classification.features import extract_features

    import ast

    f = h5py.File(filepath, "r")
    keys = list(f.keys())

    stats = {}
    for key in keys:
        parsed = ast.literal_eval(key)
        label = parsed[1]
        iq_256 = np.array(f[key])
        feats = extract_features(iq_256)

        if label not in stats:
            stats[label] = {k: [] for k in feats}
        for k, v in feats.items():
            stats[label][k].append(v)

    f.close()

    print("\nFeature statistics per class:")
    print(f"{'Label':<22} {'Samples':>8} {'peak_ratio':>12} {'bw_ratio':>12} {'flatness':>12} "
          f"{'kurtosis':>12} {'rolloff':>12}")
    print("-" * 90)

    for label in sorted(stats.keys()):
        s = stats[label]
        n = len(s['peak_ratio'])
        print(f"{label:<22} {n:>8} "
              f"{np.mean(s['peak_ratio']):>12.4f} "
              f"{np.mean(s['bw_ratio']):>12.4f} "
              f"{np.mean(s['flatness']):>12.4f} "
              f"{np.mean(s['kurtosis']):>12.4f} "
              f"{np.mean(s['rolloff']):>12.4f}")

    return stats


if __name__ == "__main__":
    if "--verify" in sys.argv:
        verify_dataset()
    else:
        print("Generating synthetic signals with augmentations...")
        generate_dataset(samples_per_class_per_snr=100, friendly_samples_per_snr=30)
        print("\nVerifying...")
        verify_dataset()
