"""
Aggressive retraining pipeline for FindMyForce signal classifier.

Focus: fix 0% recall on AM radio, Air-Ground-MTI, Airborne-detection.
Root cause: massive class imbalance (14K friendly vs 2K hostile) and
synthetic signals not matching real server signals closely enough.
"""

import os
import sys
import ast
import json
import time
import numpy as np
import h5py

sys.path.insert(0, os.path.dirname(__file__))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "generate_synthetic",
    os.path.join(os.path.dirname(__file__), "test", "generate_synthetic.py"),
)
_gs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gs)
N_SAMPLES = _gs.N_SAMPLES
to_iq_256 = _gs.to_iq_256
add_noise = _gs.add_noise
apply_augmentations = _gs.apply_augmentations
gen_pulsed_radar = _gs.gen_pulsed_radar

from scipy.ndimage import gaussian_filter1d


# ─── Improved signal generators with more variation ───────────────────────

def gen_am_radio_v2(n=N_SAMPLES, snr_db=10):
    """AM radio with more realistic variations."""
    t = np.arange(n) / n
    carrier_freq = np.random.randint(15, 60)
    carrier = np.exp(1j * 2 * np.pi * carrier_freq * t)

    # More varied audio: speech-like random spectrum
    num_tones = np.random.randint(1, 8)
    audio = np.zeros(n)
    for _ in range(num_tones):
        freq = np.random.uniform(0.3, 12)
        amp = np.random.uniform(0.02, 0.6)
        audio += amp * np.cos(2 * np.pi * freq * t + np.random.uniform(0, 2 * np.pi))

    # Sometimes add noise-like audio (speech envelope)
    if np.random.random() < 0.4:
        noise_audio = np.random.randn(n) * 0.1
        noise_audio = gaussian_filter1d(noise_audio, sigma=np.random.uniform(2, 8))
        audio += noise_audio

    mod_depth = np.random.uniform(0.15, 0.95)
    signal = (1.0 + mod_depth * audio) * carrier

    # Vary augmentation probability
    signal = apply_augmentations(signal, aug_prob=0.8)
    return add_noise(signal, snr_db)


def gen_airborne_detection_v2(n=N_SAMPLES, snr_db=10):
    """Surveillance radar with wider parameter range."""
    carrier = np.random.randint(5, 60)
    pw = np.random.uniform(0.05, 0.25)
    prf = np.random.uniform(1.5, 5.0)
    bw = np.random.randint(5, 22)
    signal = gen_pulsed_radar(n, pulse_width_frac=pw, prf_cycles=prf,
                              carrier_freq_bin=carrier, bw_bins=bw)
    # Sometimes add secondary returns (clutter)
    if np.random.random() < 0.3:
        clutter = 0.2 * np.random.randn(n) + 0.2j * np.random.randn(n)
        clutter = gaussian_filter1d(clutter.real, sigma=3) + 1j * gaussian_filter1d(clutter.imag, sigma=3)
        signal = signal + clutter

    signal = apply_augmentations(signal, aug_prob=0.8)
    return add_noise(signal, snr_db)


def gen_airborne_range_v2(n=N_SAMPLES, snr_db=10):
    """Range-finding radar with wider parameter range."""
    carrier = np.random.randint(10, 58)
    pw = np.random.uniform(0.02, 0.15)
    prf = np.random.uniform(3.0, 9.0)
    bw = np.random.randint(2, 14)
    signal = gen_pulsed_radar(n, pulse_width_frac=pw, prf_cycles=prf,
                              carrier_freq_bin=carrier, bw_bins=bw)
    signal = apply_augmentations(signal, aug_prob=0.8)
    return add_noise(signal, snr_db)


def gen_air_ground_mti_v2(n=N_SAMPLES, snr_db=10):
    """MTI radar with stronger distinguishing features."""
    carrier = np.random.randint(5, 60)
    pw = np.random.uniform(0.08, 0.30)
    prf = np.random.uniform(2.0, 7.0)
    bw = np.random.randint(8, 25)
    signal = gen_pulsed_radar(n, pulse_width_frac=pw, prf_cycles=prf,
                              carrier_freq_bin=carrier, bw_bins=bw)

    t = np.arange(n) / n
    # Strong Doppler from ground clutter + moving targets
    doppler = np.random.uniform(0.5, 15)
    signal *= np.exp(1j * 2 * np.pi * doppler * t)

    # MTI-specific: sometimes stagger the PRF
    if np.random.random() < 0.4:
        stagger = np.random.uniform(0.8, 1.2, size=n)
        stagger = gaussian_filter1d(stagger, sigma=5)
        t_mod = t * stagger
        signal *= np.exp(1j * 2 * np.pi * np.random.uniform(1, 5) * t_mod)

    signal = apply_augmentations(signal, aug_prob=0.8)
    return add_noise(signal, snr_db)


def gen_ew_jammer_v2(n=N_SAMPLES, snr_db=10):
    """EW jammer - keep similar but ensure it's clearly noise-like."""
    bw_fraction = np.random.uniform(0.5, 0.95)
    noise = np.random.randn(n) + 1j * np.random.randn(n)

    fft = np.fft.fft(noise)
    center = np.random.randint(n // 4, 3 * n // 4)
    bw = int(bw_fraction * n / 2)
    mask = np.zeros(n)
    low = max(0, center - bw)
    high = min(n, center + bw)
    mask[low:high] = 1.0
    # Smooth mask edges
    mask = gaussian_filter1d(mask, sigma=2)
    fft *= mask
    signal = np.fft.ifft(fft)
    signal = signal / (np.max(np.abs(signal)) + 1e-12)

    if np.random.random() < 0.3:
        t = np.arange(n) / n
        burst_freq = np.random.uniform(1, 5)
        envelope = 0.5 + 0.5 * np.cos(2 * np.pi * burst_freq * t)
        signal *= envelope

    signal = apply_augmentations(signal, aug_prob=0.8)
    return add_noise(signal, snr_db)


def gen_radar_altimeter_v2(n=N_SAMPLES, snr_db=10):
    """Radar altimeter augmentation."""
    t = np.arange(n) / n
    carrier = np.random.randint(20, 60)
    sweep_bw = np.random.uniform(1, 12)
    phase = 2 * np.pi * (carrier * t + 0.5 * sweep_bw * t ** 2)
    signal = np.exp(1j * phase)
    signal = apply_augmentations(signal, aug_prob=0.8)
    return add_noise(signal, snr_db)


def gen_satcom_v2(n=N_SAMPLES, snr_db=10):
    """Satcom augmentation."""
    t = np.arange(n) / n
    carrier = np.random.randint(15, 58)
    sym_rate = np.random.randint(3, 20)
    # Mix BPSK and QPSK
    if np.random.random() < 0.5:
        symbols = np.random.choice([0, np.pi], size=sym_rate)
    else:
        symbols = np.random.choice([0, np.pi / 2, np.pi, 3 * np.pi / 2], size=sym_rate)
    phase_mod = np.zeros(n)
    sps = n // sym_rate
    for i, sym in enumerate(symbols):
        s, e = i * sps, min(n, (i + 1) * sps)
        phase_mod[s:e] = sym
    phase = 2 * np.pi * carrier * t + phase_mod
    signal = np.exp(1j * phase)
    signal = apply_augmentations(signal, aug_prob=0.8)
    return add_noise(signal, snr_db)


def gen_short_range_v2(n=N_SAMPLES, snr_db=10):
    """Short-range augmentation."""
    t = np.arange(n) / n
    carrier = np.random.randint(10, 55)
    sym_rate = np.random.randint(3, 16)
    bits = np.random.choice([0.0, 1.0], size=sym_rate)
    envelope = np.zeros(n)
    sps = n // sym_rate
    for i, bit in enumerate(bits):
        s, e = i * sps, min(n, (i + 1) * sps)
        envelope[s:e] = bit
    envelope = gaussian_filter1d(envelope, sigma=np.random.uniform(0.5, 3.0))
    signal = envelope * np.exp(1j * 2 * np.pi * carrier * t)
    signal = apply_augmentations(signal, aug_prob=0.8)
    return add_noise(signal, snr_db)


# ─── Data generation ─────────────────────────────────────────────────────

GENERATORS_V2 = {
    "AM radio": gen_am_radio_v2,
    "Air-Ground-MTI": gen_air_ground_mti_v2,
    "Airborne-detection": gen_airborne_detection_v2,
    "Airborne-range": gen_airborne_range_v2,
    "EW-Jammer": gen_ew_jammer_v2,
    "Radar-Altimeter": gen_radar_altimeter_v2,
    "Satcom": gen_satcom_v2,
    "short-range": gen_short_range_v2,
}

SNR_RANGE = list(range(-20, 20, 2))  # 20 SNR levels


def generate_balanced_dataset(samples_per_snr=200, output_file=None):
    """Generate a large balanced dataset for all 8 classes."""
    if output_file is None:
        output_file = os.path.join(os.path.dirname(__file__), "dataset", "synthetic_hostile.hdf5")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    total = 0
    with h5py.File(output_file, "w") as f:
        for label, gen_fn in GENERATORS_V2.items():
            count = 0
            for snr in SNR_RANGE:
                for i in range(samples_per_snr):
                    signal = gen_fn(snr_db=snr)
                    iq_256 = to_iq_256(signal)
                    key = str(("synthetic", label, snr, i))
                    f.create_dataset(key, data=iq_256)
                    count += 1
                    total += 1
            print(f"  {label}: {count} samples")

    print(f"\nTotal: {total} samples -> {output_file}")
    return output_file


# ─── Model building ──────────────────────────────────────────────────────

def build_improved_model(num_classes=8):
    """Improved 1D CNN with BatchNorm and residual-like connections."""
    import tensorflow as tf
    from tensorflow.keras import layers, Model

    inp = layers.Input(shape=(128, 2))

    # Block 1
    x = layers.Conv1D(64, 7, padding="same")(inp)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)
    x = layers.MaxPooling1D(2)(x)

    # Block 2
    x = layers.Conv1D(128, 5, padding="same")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)
    x = layers.MaxPooling1D(2)(x)

    # Block 3
    x = layers.Conv1D(256, 3, padding="same")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)

    # Block 4
    x = layers.Conv1D(256, 3, padding="same")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)
    x = layers.GlobalAveragePooling1D()(x)

    # Dense head
    x = layers.Dense(128, activation="relu")(x)
    x = layers.Dropout(0.4)(x)
    x = layers.Dense(64, activation="relu")(x)
    x = layers.Dropout(0.3)(x)
    out = layers.Dense(num_classes, activation="softmax")(x)

    model = Model(inp, out)
    return model


# ─── Training ────────────────────────────────────────────────────────────

ALL_LABELS = [
    "Air-Ground-MTI", "Airborne-detection", "Airborne-range",
    "AM radio", "EW-Jammer", "Radar-Altimeter", "Satcom", "short-range",
]


def load_all_data():
    """Load original + synthetic + eval feedback data."""
    X, y = [], []

    # Original training data
    path = os.path.join(os.path.dirname(__file__), "dataset", "training_data.hdf5")
    f = h5py.File(path, "r")
    for key in f.keys():
        parsed = ast.literal_eval(key)
        label = parsed[1]
        if label not in ALL_LABELS:
            continue
        iq_raw = np.array(f[key], dtype=np.float32)
        i_data, q_data = iq_raw[:128], iq_raw[128:]
        X.append(np.stack([i_data, q_data], axis=-1))
        y.append(ALL_LABELS.index(label))
    f.close()
    orig_count = len(X)
    print(f"  Original: {orig_count}")

    # Synthetic data
    syn_path = os.path.join(os.path.dirname(__file__), "dataset", "synthetic_hostile.hdf5")
    if os.path.exists(syn_path):
        f = h5py.File(syn_path, "r")
        syn_count = 0
        for key in f.keys():
            parsed = ast.literal_eval(key)
            label = parsed[1]
            if label not in ALL_LABELS:
                continue
            iq_raw = np.array(f[key], dtype=np.float32)
            i_data, q_data = iq_raw[:128], iq_raw[128:]
            X.append(np.stack([i_data, q_data], axis=-1))
            y.append(ALL_LABELS.index(label))
            syn_count += 1
        f.close()
        print(f"  Synthetic: {syn_count}")

    # Eval feedback (only high-confidence correct classes)
    fb_dir = os.path.join(os.path.dirname(__file__), "dataset", "eval_feedback")
    if os.path.exists(fb_dir):
        fb_count = 0
        for fname in os.listdir(fb_dir):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(fb_dir, fname)) as f:
                data = json.load(f)
            good = {c["label"] for c in data.get("per_class_scores", []) if c.get("f1", 0) > 0.7}
            for obs in data.get("observations", []):
                lbl = obs.get("our_label")
                if lbl and lbl in good and lbl in ALL_LABELS:
                    iq = np.array(obs["iq_snapshot"], dtype=np.float32)
                    X.append(np.stack([iq[:128], iq[128:]], axis=-1))
                    y.append(ALL_LABELS.index(lbl))
                    fb_count += 1
        print(f"  Eval feedback: {fb_count}")

    return np.array(X), np.array(y)


def compute_class_weights(y, labels):
    """Compute weights to balance classes. Give EXTRA weight to weak classes."""
    from collections import Counter
    counts = Counter(y.tolist())
    total = len(y)
    n_classes = len(labels)
    weights = {}
    for i in range(n_classes):
        c = counts.get(i, 1)
        weights[i] = total / (n_classes * c)
    # Extra boost for historically weak classes
    weak_boost = {"AM radio": 2.0, "Air-Ground-MTI": 2.0, "Airborne-detection": 2.0, "Airborne-range": 1.5}
    for lbl, boost in weak_boost.items():
        idx = labels.index(lbl)
        weights[idx] *= boost
    # Slightly reduce EW-Jammer weight (over-predicted)
    weights[labels.index("EW-Jammer")] *= 0.7
    return weights


def train():
    """Full retraining pipeline."""
    import tensorflow as tf

    print("=" * 60)
    print("  FindMyForce Signal Classifier - Retraining")
    print("=" * 60)

    # Step 1: Generate more synthetic data
    print("\n[1/4] Generating balanced synthetic dataset...")
    generate_balanced_dataset(samples_per_snr=250)

    # Step 2: Load all data
    print("\n[2/4] Loading all training data...")
    X, y = load_all_data()

    unique, counts = np.unique(y, return_counts=True)
    print(f"\n  Total: {len(X)} samples, {len(unique)} classes")
    for idx, count in zip(unique, counts):
        print(f"    {ALL_LABELS[idx]:<22} {count:>6}")

    # Shuffle
    perm = np.random.permutation(len(X))
    X, y = X[perm], y[perm]

    # Split 90/10
    split = int(0.9 * len(X))
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    # Step 3: Build and train model
    print("\n[3/4] Building improved model...")
    model = build_improved_model(num_classes=len(ALL_LABELS))
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.summary()

    class_weights = compute_class_weights(y_train, ALL_LABELS)
    print("\n  Class weights:")
    for i, lbl in enumerate(ALL_LABELS):
        print(f"    {lbl:<22} {class_weights[i]:.3f}")

    callbacks = [
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6, verbose=1
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_accuracy", patience=12, restore_best_weights=True, verbose=1
        ),
    ]

    print("\n  Training...")
    model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=60,
        batch_size=128,
        class_weight=class_weights,
        callbacks=callbacks,
    )

    # Step 4: Save
    model_path = os.path.join(os.path.dirname(__file__), "models", "signal_classifier.keras")
    model.save(model_path)
    print(f"\n[4/4] Model saved to {model_path}")

    # Quick validation
    print("\n  Validation per-class accuracy:")
    val_pred = model.predict(X_val, verbose=0)
    val_pred_labels = np.argmax(val_pred, axis=1)
    for i, lbl in enumerate(ALL_LABELS):
        mask = y_val == i
        if mask.sum() == 0:
            continue
        acc = (val_pred_labels[mask] == i).mean()
        print(f"    {lbl:<22} {acc:.1%}  ({mask.sum()} samples)")

    total_acc = (val_pred_labels == y_val).mean()
    print(f"\n  Overall val accuracy: {total_acc:.1%}")
    return model


if __name__ == "__main__":
    train()
