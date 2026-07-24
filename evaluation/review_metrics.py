"""Calculate precision from a completed mapping-review CSV.

The review CSV represents detector candidates only. Therefore precision and
false positives can be calculated from it. Recall requires a manual count of
PII missed in the original document, supplied with ``--missed-pii``. Accuracy
also requires a separately annotated negative sample and is reported as N/A
unless ``--true-negatives`` is supplied.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _is_yes(value: str) -> bool:
    return value.strip().casefold() in {"yes", "y", "true", "1"}


def calculate(
    review_path: Path,
    missed_pii: int | None = None,
    true_negatives: int | None = None,
) -> dict[str, object]:
    """Calculate reviewed mapping metrics."""
    with review_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise ValueError("Review CSV is empty")
    if any(not row.get("is_actual_pii", "").strip() for row in rows):
        raise ValueError("Every row must have is_actual_pii set to yes or no")

    true_positive = sum(_is_yes(row["is_actual_pii"]) for row in rows)
    false_positive = len(rows) - true_positive
    true_positive_occurrences = sum(
        int(row.get("original_occurrences") or 1)
        for row in rows
        if _is_yes(row["is_actual_pii"])
    )
    false_positive_occurrences = sum(
        int(row.get("original_occurrences") or 1)
        for row in rows
        if not _is_yes(row["is_actual_pii"])
    )
    precision = true_positive / len(rows) if rows else 0.0
    metrics: dict[str, object] = {
        "Reviewed candidates": len(rows),
        "True positives": true_positive,
        "False positives": false_positive,
        "True-positive occurrences": true_positive_occurrences,
        "False-positive occurrences": false_positive_occurrences,
        "Precision": precision,
        "Recall": "N/A (supply --missed-pii)",
        "F1 Score": "N/A (supply --missed-pii)",
        "Accuracy": "N/A (supply --true-negatives)",
    }
    if missed_pii is not None:
        recall = true_positive / (true_positive + missed_pii)
        metrics["Missed PII"] = missed_pii
        metrics["Recall"] = recall
        metrics["F1 Score"] = (
            2 * precision * recall / (precision + recall)
            if precision + recall else 0.0
        )
    if true_negatives is not None:
        denominator = true_positive + false_positive + (missed_pii or 0) + true_negatives
        metrics["True negatives"] = true_negatives
        metrics["Accuracy"] = (
            (true_positive + true_negatives) / denominator
            if denominator else 0.0
        )
    return metrics


def main() -> None:
    """Calculate and print reviewed mapping metrics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review", type=Path)
    parser.add_argument("--missed-pii", type=int)
    parser.add_argument("--true-negatives", type=int)
    args = parser.parse_args()
    metrics = calculate(args.review, args.missed_pii, args.true_negatives)
    for name, value in metrics.items():
        print(f"{name}: {value:.4f}" if isinstance(value, float) else f"{name}: {value}")


if __name__ == "__main__":
    main()
