import sys
import time
from collections import Counter

from findmyforce.util.api_server import (
    get_observations, get_scores, stream_observations,
    get_status, get_eval_observations, submit_eval,
    is_rate_limited, cooldown_remaining,
)
from findmyforce.pipeline.processor import (
    process_observations, classify_batch_fast, submit_batch,
)


def run():
    """Fetch observations via polling, process with grouping, and submit."""
    print("Fetching observations...")
    data = get_observations(limit=50)
    observations = data["observations"]
    print(f"  {len(observations)} observations")

    if not observations:
        print("  No observations available.")
        return []

    print("Processing with grouping...")
    submissions = process_observations(observations)
    _print_and_submit(submissions)
    return submissions


def run_stream(batch_size=20, batch_timeout_s=3.0):
    """
    Process observations in real-time via SSE streaming.

    Uses fast batch classification (no grouping) for minimum latency.
    During rate-limit cooldown, classifies and logs without submitting.
    """
    print("Connecting to SSE stream...")
    print("  Press Ctrl+C to stop\n")

    buffer = []
    last_submit = time.time()
    total_accepted = 0
    total_rejected = 0
    total_skipped = 0
    label_correct = Counter()
    label_total = Counter()

    try:
        for obs in stream_observations():
            buffer.append(obs)
            now = time.time()
            elapsed = now - last_submit

            if len(buffer) >= batch_size or (buffer and elapsed >= batch_timeout_s):
                t0 = time.time()
                submissions = classify_batch_fast(buffer)
                t_classify = time.time() - t0

                if not submissions:
                    buffer = []
                    last_submit = time.time()
                    continue

                labels = Counter(s["classification_label"] for s in submissions)

                # Show each classification result
                for s in submissions:
                    print(f"    {s['observation_id'][:10]}  "
                          f"{s['classification_label']:<22} "
                          f"conf={s['confidence']:.3f}  "
                          f"loc=({s['estimated_latitude']:.4f}, {s['estimated_longitude']:.4f})")

                if is_rate_limited():
                    # Cooldown mode: log only, don't submit
                    cd = cooldown_remaining()
                    total_skipped += len(submissions)
                    print(f"  [{time.strftime('%H:%M:%S')}] "
                          f"COOLDOWN ({cd:.0f}s left) — "
                          f"Classified {len(submissions)}: {dict(labels)}  "
                          f"({t_classify:.2f}s)  "
                          f"[skipped submission]")
                else:
                    # Normal mode: submit
                    result = submit_batch(submissions)
                    accepted = result.get("accepted_count", 0)
                    rejected = result.get("rejected_count", 0)
                    total_accepted += accepted
                    total_rejected += rejected

                    # Track per-label accuracy
                    for s in submissions:
                        label_total[s["classification_label"]] += 1
                    # Approximate: accepted = correct predictions
                    if accepted == len(submissions):
                        for s in submissions:
                            label_correct[s["classification_label"]] += 1

                    acc = total_accepted / max(1, total_accepted + total_rejected) * 100
                    print(f"  [{time.strftime('%H:%M:%S')}] "
                          f"Batch {len(submissions)}: {dict(labels)}  "
                          f"({t_classify:.2f}s)  "
                          f"accepted={accepted}  "
                          f"| total: {total_accepted}/{total_accepted + total_rejected} "
                          f"({acc:.1f}%)")

                buffer = []
                last_submit = time.time()

    except KeyboardInterrupt:
        if buffer:
            submissions = classify_batch_fast(buffer)
            if submissions and not is_rate_limited():
                submit_batch(submissions)

        total = total_accepted + total_rejected
        acc = total_accepted / max(1, total) * 100
        print(f"\nStopped. Total: {total_accepted} accepted, {total_rejected} rejected "
              f"({acc:.1f}% accuracy), {total_skipped} skipped (cooldown)")

        # Show per-label accuracy
        if label_total:
            print("\nPer-label stats:")
            print(f"  {'Label':<22} {'Submitted':>10} {'Correct':>10} {'Accuracy':>10}")
            print(f"  {'-'*54}")
            for lbl in sorted(label_total.keys()):
                t = label_total[lbl]
                c = label_correct[lbl]
                a = c / max(1, t) * 100
                print(f"  {lbl:<22} {t:>10} {c:>10} {a:>9.1f}%")

        scores = get_scores()
        print(f"\nScores: total={scores.get('total_score', 0):.1f}  "
              f"classification={scores.get('classification_score', 0):.1f}  "
              f"geolocation={scores.get('geolocation_score', 0):.1f}  "
              f"novelty={scores.get('novelty_detection_score', 0):.1f}")


def run_eval():
    """
    Fetch evaluation observations, classify, geolocate, submit, and print scores.

    Only works when evaluation_open=true on the server.
    """
    # Check server state
    status = get_status()
    print(f"Server: {status.get('simulation_state', '?')}  "
          f"eval_open: {status.get('evaluation_open', False)}")

    if not status.get("evaluation_open", False):
        print("Evaluation is not open yet. Run with --stream to collect live data.")
        return None

    # Fetch eval observations
    print("Fetching evaluation observations...")
    data = get_eval_observations()
    eval_obs = data.get("observations", [])
    print(f"  {len(eval_obs)} evaluation observations")

    if not eval_obs:
        print("  No evaluation observations available.")
        return None

    # Classify and geolocate
    print("Classifying...")
    submissions = classify_batch_fast(eval_obs)
    print(f"  {len(submissions)} submissions prepared")

    labels = Counter(s["classification_label"] for s in submissions)
    print(f"  Labels: {dict(labels)}")

    # Submit to evaluation endpoint
    print("\nSubmitting to evaluation endpoint...")
    result = submit_eval(submissions)

    # Print detailed results
    print(f"\n  Total Score:      {result.get('total_score', 0):.1f}")
    print(f"  Best Total Score: {result.get('best_total_score', 0):.1f}")
    print(f"  Coverage:         {result.get('coverage', 0)}%")
    print(f"  Attempt #:        {result.get('attempt_number', '?')}")

    if "classification_score" in result:
        print(f"  Classification:   {result['classification_score']:.1f}")
    if "geolocation_score" in result:
        print(f"  Geolocation:      {result['geolocation_score']:.1f}")
    if "novelty_detection_score" in result:
        print(f"  Novelty:          {result['novelty_detection_score']:.1f}")

    # Save eval results for retraining
    _save_eval_feedback(eval_obs, submissions, result)

    return result


def _save_eval_feedback(eval_obs, submissions, result):
    """Save evaluation observations and results for retraining."""
    import json
    import os

    feedback_dir = os.path.join(os.path.dirname(__file__), "..", "dataset", "eval_feedback")
    os.makedirs(feedback_dir, exist_ok=True)

    attempt = result.get("attempt_number", "unknown")
    path = os.path.join(feedback_dir, f"eval_attempt_{attempt}.json")

    # Build lookup of our predictions
    pred_lookup = {s["observation_id"]: s for s in submissions}

    feedback = {
        "attempt_number": attempt,
        "total_score": result.get("total_score", 0),
        "classification_score": result.get("classification_score", 0),
        "geolocation_score": result.get("geolocation_score", 0),
        "novelty_detection_score": result.get("novelty_detection_score", 0),
        "per_class_scores": result.get("per_class_scores", []),
        "observations": [],
    }

    for obs in eval_obs:
        oid = obs["observation_id"]
        entry = {
            "observation_id": oid,
            "receiver_id": obs["receiver_id"],
            "rssi_dbm": obs["rssi_dbm"],
            "snr_estimate_db": obs.get("snr_estimate_db"),
            "iq_snapshot": obs["iq_snapshot"],
            "our_label": pred_lookup.get(oid, {}).get("classification_label"),
            "our_confidence": pred_lookup.get(oid, {}).get("confidence"),
        }
        feedback["observations"].append(entry)

    with open(path, "w") as f:
        json.dump(feedback, f)
    print(f"  Saved feedback to {path}")


def _print_and_submit(submissions):
    """Print summary and submit."""
    if not submissions:
        print("  No submissions.")
        return

    labels = Counter(s["classification_label"] for s in submissions)
    print(f"  {len(submissions)} submissions: {dict(labels)}")

    print("\nSubmitting batch...")
    result = submit_batch(submissions)
    accepted = result.get("accepted_count", 0)
    rejected = result.get("rejected_count", 0)
    print(f"  Accepted: {accepted}, Rejected: {rejected}")

    print("\nScores:")
    scores = get_scores()
    print(f"  Total: {scores.get('total_score', 0):.1f}  "
          f"Classification: {scores.get('classification_score', 0):.1f}  "
          f"Geolocation: {scores.get('geolocation_score', 0):.1f}  "
          f"Novelty: {scores.get('novelty_detection_score', 0):.1f}")


if __name__ == "__main__":
    if "--stream" in sys.argv:
        run_stream()
    elif "--eval" in sys.argv:
        run_eval()
    else:
        run()
