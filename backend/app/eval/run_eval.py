# Raksha — Evaluation Runner
# Runs the classifier against the test set and computes metrics.
# Usage: python -m backend.app.eval.run_eval

from __future__ import annotations
import json
import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agents.classifier import ClassifierAgent
from backend.app.eval.metrics import compute_metrics, save_metrics

DATA_DIR = Path(__file__).parent.parent.parent / "data"
TEST_SET_PATH = DATA_DIR / "test_set.json"
PREDICTIONS_PATH = DATA_DIR / "eval_predictions.json"


async def run_evaluation():
    """Run the classifier on the test set and compute metrics."""
    print("=" * 60)
    print("Raksha — Evaluation Runner")
    print("=" * 60)

    # Load test set
    if not TEST_SET_PATH.exists():
        print(f"✗ Test set not found at {TEST_SET_PATH}")
        print("  Run `python -m backend.app.eval.generate_data` first.")
        sys.exit(1)

    with open(TEST_SET_PATH, "r", encoding="utf-8") as f:
        test_data = json.load(f)

    print(f"Loaded {len(test_data)} test examples.")

    # Initialize classifier
    classifier = ClassifierAgent()

    # Run predictions
    true_labels = []
    predicted_labels = []
    true_scam_types = []
    predicted_scam_types = []
    subsets = []
    predictions = []

    for i, example in enumerate(test_data):
        text = example["text"]
        true_label = example["label"]
        true_type = example.get("scam_type")
        subset = example.get("subset", "standard")

        print(f"  [{i+1}/{len(test_data)}] [{subset}] Classifying... ", end="", flush=True)

        try:
            result = await classifier.classify(text)
            pred_label = result.label
            pred_type = result.scam_type

            print(f"TRUE={true_label} PRED={pred_label} "
                  f"{'[OK]' if true_label == pred_label else '[FAIL]'} "
                  f"(conf={result.confidence:.2f})")

            true_labels.append(true_label)
            predicted_labels.append(pred_label)
            true_scam_types.append(true_type)
            predicted_scam_types.append(pred_type)
            subsets.append(subset)

            predictions.append({
                "text": text[:100] + "..." if len(text) > 100 else text,
                "true_label": true_label,
                "predicted_label": pred_label,
                "true_scam_type": true_type,
                "predicted_scam_type": pred_type,
                "confidence": result.confidence,
                "signals": result.signals,
                "correct": true_label == pred_label,
                "subset": subset,
            })

        except Exception as e:
            print(f"ERROR: {e}")
            # On error, record as UNCERTAIN (safe fallback)
            true_labels.append(true_label)
            predicted_labels.append("UNCERTAIN")
            true_scam_types.append(true_type)
            predicted_scam_types.append(None)
            subsets.append(subset)

        # Only sleep if we did not hit the cache (to stay below the 15 RPM free tier limit)
        from backend.app.llm.wrapper import get_llm
        import hashlib
        llm = get_llm()
        cache_key = hashlib.sha256(
            f"{classifier.system_prompt}:{text}:ClassificationResult".encode("utf-8")
        ).hexdigest()
        
        if cache_key in getattr(llm, "_cache", {}):
            await asyncio.sleep(0.01)
        else:
            await asyncio.sleep(4.0)

    # Compute metrics
    print("\n" + "=" * 60)
    print("Computing metrics...")
    metrics = compute_metrics(
        true_labels=true_labels,
        predicted_labels=predicted_labels,
        true_scam_types=true_scam_types,
        predicted_scam_types=predicted_scam_types,
        subsets=subsets,
    )

    # Save results
    save_metrics(metrics)

    # Save raw predictions
    with open(PREDICTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2, ensure_ascii=False)
    print(f"Predictions saved to {PREDICTIONS_PATH}")

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    print(f"  Test samples:        {metrics['n_test']}")
    print(f"  Precision (macro):   {metrics['precision']:.4f}")
    print(f"  Recall (macro):      {metrics['recall']:.4f}")
    print(f"  F1 Score (macro):    {metrics['f1']:.4f}")
    print(f"  FALSE POSITIVE RATE: {metrics['false_positive_rate']:.4f}  <- THE METRIC")
    print(f"  HARD-NEGATIVE FPR:   {metrics['hard_negative_fpr']:.4f}")
    print(f"  INJECTION RESIST:    {metrics['injection_resistance_rate']:.4f}")

    print("\nConfusion Matrix:")
    cm = metrics["confusion_matrix"]["matrix"]
    labels = metrics["confusion_matrix"]["labels"]
    print(f"  {'':>12} {'SCAM':>8} {'SAFE':>8} {'UNCRT':>8}")
    for i, label in enumerate(labels):
        row = "  ".join(f"{cm[i][j]:>8}" for j in range(3))
        print(f"  {label:>12} {row}")

    if metrics["by_subset"]:
        print("\nPer-Subset Breakdown:")
        for sub, m in metrics["by_subset"].items():
            print(f"  {sub:>20}: Acc={m['accuracy']:.2f} FPR={m['fpr']:.2f} "
                  f"P={m['precision']:.2f} R={m['recall']:.2f} F1={m['f1']:.2f} (n={m['n_samples']})")

    if metrics["by_scam_type"]:
        print("\nPer-Type Breakdown:")
        for stype, m in metrics["by_scam_type"].items():
            print(f"  {stype:>20}: P={m['precision']:.2f} R={m['recall']:.2f} "
                  f"F1={m['f1']:.2f} (n={m['count']})")

    correct = sum(1 for p in predictions if p.get("correct"))
    print(f"\nAccuracy: {correct}/{len(predictions)} = {correct/len(predictions)*100:.1f}%")
    print("\n[OK] Done. Metrics are now served at GET /metrics.")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
