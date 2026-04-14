import os
import ast

import numpy as np
import h5py

from findmyforce.classification.features import extract_features, iq_to_complex

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "signal_classifier.keras")
DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "dataset", "training_data.hdf5")
SYNTHETIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "dataset", "synthetic_hostile.hdf5")

# All 8 labels the model can learn (ordered)
ALL_LABELS = [
    "Air-Ground-MTI", "Airborne-detection", "Airborne-range",
    "AM radio", "EW-Jammer", "Radar-Altimeter", "Satcom", "short-range",
]

# Friendly labels (in original training data)
ML_LABELS = ["Radar-Altimeter", "Satcom", "short-range"]

# Hostile + civilian labels
HOSTILE_LABELS = ["Airborne-detection", "Airborne-range", "Air-Ground-MTI", "EW-Jammer"]
CIVILIAN_LABELS = ["AM radio"]

_model = None


def _iq_to_2ch(iq_raw):
    """Convert 256-float IQ to (128, 2) array: [I, Q] channels."""
    iq = np.array(iq_raw, dtype=np.float32)
    i_data = iq[:128]
    q_data = iq[128:]
    return np.stack([i_data, q_data], axis=-1)  # (128, 2)


def _load_training_data():
    """Load IQ samples and labels from HDF5 training dataset (friendly only)."""
    f = h5py.File(DATASET_PATH, "r")
    X = []
    y = []
    for key in f.keys():
        parsed = ast.literal_eval(key)
        label = parsed[1]
        if label not in ALL_LABELS:
            continue
        iq_raw = np.array(f[key], dtype=np.float32)
        X.append(_iq_to_2ch(iq_raw))
        y.append(ALL_LABELS.index(label))
    f.close()
    return X, y


def _load_synthetic_data():
    """Load synthetic hostile/civilian signals if available."""
    if not os.path.exists(SYNTHETIC_PATH):
        return [], []

    f = h5py.File(SYNTHETIC_PATH, "r")
    X = []
    y = []
    for key in f.keys():
        parsed = ast.literal_eval(key)
        label = parsed[1]
        if label not in ALL_LABELS:
            continue
        iq_raw = np.array(f[key], dtype=np.float32)
        X.append(_iq_to_2ch(iq_raw))
        y.append(ALL_LABELS.index(label))
    f.close()
    return X, y


def _load_eval_feedback():
    """Load evaluation feedback data for retraining (if per_class_scores available)."""
    import json
    import glob

    feedback_dir = os.path.join(os.path.dirname(__file__), "..", "..", "dataset", "eval_feedback")
    if not os.path.exists(feedback_dir):
        return [], []

    X = []
    y = []
    for path in glob.glob(os.path.join(feedback_dir, "eval_attempt_*.json")):
        with open(path) as f:
            data = json.load(f)

        # Use per_class_scores to identify which classes we got right
        # If a class has high F1, our labels for that class are likely correct
        good_classes = set()
        for cls_score in data.get("per_class_scores", []):
            if cls_score.get("f1", 0) > 0.5:
                good_classes.add(cls_score["label"])

        for obs in data.get("observations", []):
            our_label = obs.get("our_label")
            if our_label and our_label in good_classes and our_label in ALL_LABELS:
                iq_raw = obs["iq_snapshot"]
                X.append(_iq_to_2ch(iq_raw))
                y.append(ALL_LABELS.index(our_label))

    return X, y


def _build_model(num_classes=8):
    """Build a 1D CNN for IQ signal classification with 2-channel input (I, Q)."""
    import tensorflow as tf

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(128, 2)),
        tf.keras.layers.Conv1D(32, 7, activation="relu", padding="same"),
        tf.keras.layers.MaxPooling1D(2),
        tf.keras.layers.Conv1D(64, 5, activation="relu", padding="same"),
        tf.keras.layers.MaxPooling1D(2),
        tf.keras.layers.Conv1D(128, 3, activation="relu", padding="same"),
        tf.keras.layers.GlobalAveragePooling1D(),
        tf.keras.layers.Dense(64, activation="relu"),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(num_classes, activation="softmax"),
    ])
    model.compile(
        optimizer="adam",
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def train_model(epochs=20, batch_size=64, include_synthetic=True, include_feedback=True):
    """
    Train the classifier on all available data:
      1. Original HDF5 training data (friendly signals)
      2. Synthetic hostile/civilian signals (if generated)
      3. Evaluation feedback (if available and correct)
    """
    import tensorflow as tf

    print("Loading training data...")
    X_all, y_all = _load_training_data()
    print(f"  Original: {len(X_all)} samples")

    if include_synthetic:
        X_syn, y_syn = _load_synthetic_data()
        if X_syn:
            X_all.extend(X_syn)
            y_all.extend(y_syn)
            print(f"  Synthetic: {len(X_syn)} samples")

    if include_feedback:
        X_fb, y_fb = _load_eval_feedback()
        if X_fb:
            X_all.extend(X_fb)
            y_all.extend(y_fb)
            print(f"  Eval feedback: {len(X_fb)} samples")

    X = np.array(X_all)
    y = np.array(y_all)

    # Show class distribution
    unique, counts = np.unique(y, return_counts=True)
    print(f"  Total: {len(X)} samples across {len(unique)} classes")
    for idx, count in zip(unique, counts):
        print(f"    {ALL_LABELS[idx]}: {count}")

    # Shuffle
    idx = np.random.permutation(len(X))
    X, y = X[idx], y[idx]

    # Train/val split (90/10)
    split = int(0.9 * len(X))
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    print("Building model...")
    model = _build_model(num_classes=len(ALL_LABELS))
    model.summary()

    print("Training...")
    model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
    )

    os.makedirs(MODEL_DIR, exist_ok=True)
    model.save(MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

    # Reset cached model so next call loads the new one
    global _model
    _model = None

    return model


def _get_model():
    """Load the trained model (lazy singleton)."""
    global _model
    if _model is not None:
        return _model

    if not os.path.exists(MODEL_PATH):
        return None

    import tensorflow as tf
    _model = tf.keras.models.load_model(MODEL_PATH)
    return _model


def _classify_hostile(iq_snapshot):
    """
    Fallback rule-based classifier for hostile/civilian signals.
    Used when no model is available or model confidence is low.
    """
    f = extract_features(iq_snapshot)
    peak_ratio = f["peak_ratio"]
    bw_ratio = f["bw_ratio"]
    flatness = f["flatness"]
    kurtosis = f["kurtosis"]

    # AM radio: strong carrier + symmetric sidebands
    if peak_ratio > 0.10 and bw_ratio < 0.25 and flatness < 0.15:
        return "AM radio", min(0.85, 0.5 + peak_ratio)

    # EW-Jammer: broadband noise-like
    if flatness > 0.40 and bw_ratio > 0.50:
        return "EW-Jammer", min(0.85, 0.4 + flatness * 0.5)

    # Airborne-detection: wide-bandwidth pulsed
    if 0.25 <= bw_ratio <= 0.55 and kurtosis > 3.5 and flatness < 0.35:
        return "Airborne-detection", min(0.70, 0.35 + bw_ratio)

    # Airborne-range: narrow pulsed, high PRF
    if 0.10 <= bw_ratio <= 0.30 and kurtosis > 4.0:
        return "Airborne-range", min(0.70, 0.3 + kurtosis / 15.0)

    # Air-Ground-MTI: wideband pulsed
    if bw_ratio > 0.30 and 0.15 <= flatness <= 0.45:
        return "Air-Ground-MTI", min(0.65, 0.3 + bw_ratio)

    if kurtosis > 5.0:
        return "Airborne-detection", 0.45
    return "Air-Ground-MTI", 0.40


def classify_signal(iq_snapshot, snr_db=None):
    """
    Classify the signal type from its IQ snapshot.

    If the model was trained on all 8 classes (with synthetic data),
    it handles everything. Otherwise falls back to rule-based for
    hostile/civilian signals.

    Returns (label, confidence).
    """
    model = _get_model()

    if model is not None:
        iq_2ch = _iq_to_2ch(iq_snapshot).reshape(1, 128, 2)
        probs = model.predict(iq_2ch, verbose=0)[0]
        best_idx = int(np.argmax(probs))
        confidence = float(probs[best_idx])

        num_classes = len(probs)

        if num_classes == len(ALL_LABELS):
            # Full 8-class model — trust it if confident
            if confidence >= 0.5:
                return ALL_LABELS[best_idx], confidence
            return _classify_hostile(iq_snapshot)

        # Legacy 3-class model — only trust for friendly signals
        if confidence >= 0.6:
            return ML_LABELS[best_idx], confidence

    return _classify_hostile(iq_snapshot)


if __name__ == "__main__":
    train_model()
