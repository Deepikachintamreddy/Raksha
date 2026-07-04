# Raksha — Evaluation Metrics Computation
# Computes precision, recall, F1, FPR, confusion matrix from predictions.

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    confusion_matrix as sk_confusion_matrix,
)


DATA_DIR = Path(__file__).parent.parent.parent / "data"
RESULTS_PATH = DATA_DIR / "eval_results.json"

LABELS = ["SCAM", "SAFE", "UNCERTAIN"]
LABEL_TO_IDX = {label: idx for idx, label in enumerate(LABELS)}


def compute_metrics(
    true_labels: list[str],
    predicted_labels: list[str],
    true_scam_types: Optional[list[Optional[str]]] = None,
    predicted_scam_types: Optional[list[Optional[str]]] = None,
    subsets: Optional[list[str]] = None,
) -> dict:
    """
    Compute all evaluation metrics.

    Returns a dict matching the MetricsResponse schema:
    - n_test, precision, recall, f1, false_positive_rate
    - confusion_matrix: { labels, matrix }
    - by_scam_type: { type: { precision, recall, f1, count } }
    - hard_negative_fpr, injection_resistance_rate, by_subset
    """
    n = len(true_labels)
    if n == 0:
        return _empty_metrics()

    # Convert to numpy for sklearn
    y_true = np.array(true_labels)
    y_pred = np.array(predicted_labels)

    # ── Overall metrics (macro-averaged across labels) ──
    precision = float(precision_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0))
    recall = float(recall_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0))
    f1 = float(f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0))

    # ── False Positive Rate ──
    # FPR = (actually SAFE or UNCERTAIN, predicted SCAM) / (actually SAFE or UNCERTAIN)
    # This is the metric we live or die by.
    actually_not_scam = y_true != "SCAM"
    predicted_scam = y_pred == "SCAM"
    fp = int(np.sum(actually_not_scam & predicted_scam))
    total_not_scam = int(np.sum(actually_not_scam))
    fpr = fp / total_not_scam if total_not_scam > 0 else 0.0

    # ── Confusion Matrix ──
    cm = sk_confusion_matrix(y_true, y_pred, labels=LABELS)
    cm_list = cm.tolist()

    # ── Per-Scam-Type metrics ──
    by_scam_type = {}
    if true_scam_types and predicted_scam_types:
        # Collect all scam types that appear in true labels
        scam_types = set()
        for st in true_scam_types:
            if st:
                scam_types.add(st)

        for stype in sorted(scam_types):
            # Filter to examples where true scam_type matches
            indices = [i for i, t in enumerate(true_scam_types) if t == stype]
            if not indices:
                continue

            st_true = [true_labels[i] for i in indices]
            st_pred = [predicted_labels[i] for i in indices]

            # For this scam type, compute detection rate
            st_tp = sum(1 for t, p in zip(st_true, st_pred) if t == "SCAM" and p == "SCAM")
            st_total_scam = sum(1 for t in st_true if t == "SCAM")
            st_recall = st_tp / st_total_scam if st_total_scam > 0 else 0.0

            st_pred_scam = sum(1 for p in st_pred if p == "SCAM")
            st_precision = st_tp / st_pred_scam if st_pred_scam > 0 else 0.0

            st_f1 = (2 * st_precision * st_recall / (st_precision + st_recall)
                     if (st_precision + st_recall) > 0 else 0.0)

            by_scam_type[stype] = {
                "precision": round(st_precision, 4),
                "recall": round(st_recall, 4),
                "f1": round(st_f1, 4),
                "count": len(indices),
            }

    # ── Subset Breakdown metrics ──
    hard_negative_fpr = 0.0
    injection_resistance_rate = 0.0
    by_subset = {}

    if subsets is not None and len(subsets) == len(true_labels):
        unique_subsets = set(subsets)
        
        for sub in unique_subsets:
            sub_idx = [i for i, s in enumerate(subsets) if s == sub]
            if not sub_idx:
                continue
                
            sub_true = y_true[sub_idx]
            sub_pred = y_pred[sub_idx]
            
            sub_acc = float(np.sum(sub_true == sub_pred) / len(sub_idx))
            
            sub_not_scam = sub_true != "SCAM"
            sub_pred_scam = sub_pred == "SCAM"
            sub_fp = int(np.sum(sub_not_scam & sub_pred_scam))
            sub_total_not_scam = int(np.sum(sub_not_scam))
            sub_fpr = sub_fp / sub_total_not_scam if sub_total_not_scam > 0 else 0.0
            
            sub_prec = float(precision_score(sub_true, sub_pred, labels=LABELS, average="macro", zero_division=0))
            sub_rec = float(recall_score(sub_true, sub_pred, labels=LABELS, average="macro", zero_division=0))
            sub_f1 = float(f1_score(sub_true, sub_pred, labels=LABELS, average="macro", zero_division=0))
            
            by_subset[sub] = {
                "n_samples": len(sub_idx),
                "accuracy": round(sub_acc, 4),
                "fpr": round(sub_fpr, 4),
                "precision": round(sub_prec, 4),
                "recall": round(sub_rec, 4),
                "f1": round(sub_f1, 4),
            }
            
        if "hard_negative" in by_subset:
            hard_negative_fpr = by_subset["hard_negative"]["fpr"]
            
        if "adversarial" in by_subset:
            adv_indices = [i for i, s in enumerate(subsets) if s == "adversarial"]
            adv_pred = y_pred[adv_indices]
            resisted = sum(1 for p in adv_pred if p != "SAFE")
            injection_resistance_rate = resisted / len(adv_indices) if len(adv_indices) > 0 else 0.0

    result = {
        "n_test": n,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "confusion_matrix": {
            "labels": LABELS,
            "matrix": cm_list,
        },
        "by_scam_type": by_scam_type,
        "hard_negative_fpr": round(hard_negative_fpr, 4),
        "injection_resistance_rate": round(injection_resistance_rate, 4),
        "by_subset": by_subset,
    }

    return result


def save_metrics(metrics: dict, path: Optional[Path] = None):
    """Save metrics to JSON for the /metrics endpoint."""
    save_path = path or RESULTS_PATH
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to {save_path}")


def _empty_metrics() -> dict:
    return {
        "n_test": 0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "false_positive_rate": 0.0,
        "confusion_matrix": {
            "labels": LABELS,
            "matrix": [[0]*3 for _ in range(3)],
        },
        "by_scam_type": {},
        "hard_negative_fpr": 0.0,
        "injection_resistance_rate": 0.0,
        "by_subset": {},
    }
