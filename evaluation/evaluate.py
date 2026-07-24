"""Evaluate detector output against manually annotated JSON ground truth.

Ground-truth format::

    {
      "documents": [
        {
          "id": "document-1",
          "text": "Contact Rashi Patil at rashi@example.com.",
          "entities": [
            {"start": 8, "end": 19, "entity_type": "PERSON"},
            {"start": 23, "end": 42, "entity_type": "EMAIL"}
          ]
        }
      ]
    }

Entity precision, recall, and F1 use exact span and type matching. Accuracy
is reported at character level because extraction datasets do not provide a
natural entity-level true-negative count.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from src.detector import PIIDetector


def _load_ground_truth(path: Path) -> list[dict[str, Any]]:
    """Load and validate annotated documents."""
    data = json.loads(path.read_text(encoding="utf-8"))
    documents = data.get("documents") if isinstance(data, dict) else None
    if not isinstance(documents, list) or not documents:
        raise ValueError("Ground truth must contain a non-empty 'documents' list")
    for document in documents:
        if not isinstance(document, dict):
            raise ValueError("Each ground-truth document must be an object")
        if not isinstance(document.get("text"), str):
            raise ValueError("Each document requires a string 'text' field")
        if not isinstance(document.get("entities"), list):
            raise ValueError("Each document requires an 'entities' list")
    return documents


def _entity_key(entity: Any) -> tuple[int, int, str]:
    """Convert a detector or annotation entity to a comparable key."""
    if isinstance(entity, dict):
        return int(entity["start"]), int(entity["end"]), str(entity["entity_type"])
    return entity.start, entity.end, entity.entity_type


def evaluate_documents(documents: list[dict[str, Any]]) -> dict[str, object]:
    """Evaluate exact entity matches and character-level classification."""
    detector = PIIDetector()
    true_positive = false_positive = false_negative = 0
    truth_counts: Counter[str] = Counter()
    prediction_counts: Counter[str] = Counter()
    truth_labels: list[int] = []
    prediction_labels: list[int] = []

    for document in documents:
        text = document["text"]
        truth = {_entity_key(entity) for entity in document["entities"]}
        predictions = {_entity_key(entity) for entity in detector.detect(text)}
        truth_positive = truth & predictions
        true_positive += len(truth_positive)
        false_positive += len(predictions - truth)
        false_negative += len(truth - predictions)
        truth_counts.update(entity[2] for entity in truth)
        prediction_counts.update(entity[2] for entity in predictions)

        truth_labels.extend(_character_labels(text, truth))
        prediction_labels.extend(_character_labels(text, predictions))

    precision = precision_score(
        [1] * true_positive + [0] * false_positive,
        [1] * true_positive + [1] * false_positive,
        zero_division=0,
    ) if true_positive + false_positive else 0.0
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative else 0.0
    )
    f1 = f1_score(
        [1] * true_positive + [0] * false_positive + [1] * false_negative,
        [1] * true_positive + [1] * false_positive + [0] * false_negative,
        zero_division=0,
    ) if true_positive + false_positive + false_negative else 0.0

    return {
        "Total ground-truth entities": sum(truth_counts.values()),
        "Total detected entities": sum(prediction_counts.values()),
        "True positives": true_positive,
        "False positives": false_positive,
        "False negatives": false_negative,
        "Precision": float(precision),
        "Recall": float(recall),
        "F1 Score": float(f1),
        "Accuracy": float(accuracy_score(truth_labels, prediction_labels)),
        "Ground-truth entity counts": dict(sorted(truth_counts.items())),
        "Detected entity counts": dict(sorted(prediction_counts.items())),
    }


def _character_labels(text: str, entities: set[tuple[int, int, str]]) -> list[int]:
    """Create binary character-level PII labels for accuracy calculation."""
    labels = [0] * len(text)
    for start, end, _ in entities:
        if start < 0 or end < start or end > len(text):
            raise ValueError(f"Invalid entity span: {(start, end)}")
        for index in range(start, end):
            labels[index] = 1
    return labels


def _write_reports(metrics: dict[str, object], report_path: Path, csv_path: Path) -> None:
    """Write text and CSV evaluation reports."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as report:
        report.write("PII Redaction Evaluation Report\n")
        report.write("=" * 34 + "\n")
        for name, value in metrics.items():
            if isinstance(value, float):
                report.write(f"{name}: {value:.4f}\n")
            else:
                report.write(f"{name}: {value}\n")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        csv_file.write("Metric,Value\n")
        for name, value in metrics.items():
            if isinstance(value, dict):
                value = json.dumps(value, sort_keys=True)
            csv_file.write(f"{name},{value}\n")


def main() -> None:
    """Run evaluation from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("--report", type=Path, default=Path("output/evaluation_report.txt"))
    parser.add_argument("--csv", type=Path, default=Path("output/evaluation_metrics.csv"))
    args = parser.parse_args()
    metrics = evaluate_documents(_load_ground_truth(args.ground_truth))
    _write_reports(metrics, args.report, args.csv)
    print(f"Wrote {args.report} and {args.csv}")


if __name__ == "__main__":
    main()
