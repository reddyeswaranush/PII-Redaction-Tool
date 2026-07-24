"""Evaluation reports for labelled experiments and production runs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from .config import METRICS_FILE, REPORT_FILE

LOGGER = logging.getLogger(__name__)


class Evaluator:
    """Compute standard metrics and write human- and machine-readable reports."""

    def evaluate(self, ground_truth: Sequence[int], predictions: Sequence[int]) -> dict[str, float]:
        """Return accuracy, precision, recall, and F1 for aligned labels."""
        if len(ground_truth) != len(predictions):
            raise ValueError("ground_truth and predictions must have equal length")
        return {
            "Accuracy": float(accuracy_score(ground_truth, predictions)),
            "Precision": float(precision_score(ground_truth, predictions, zero_division=0)),
            "Recall": float(recall_score(ground_truth, predictions, zero_division=0)),
            "F1 Score": float(f1_score(ground_truth, predictions, zero_division=0)),
        }

    def save_metrics(
        self, metrics: Mapping[str, object], path: Path = METRICS_FILE,
    ) -> None:
        """Save metrics, including unavailable values, as a two-column CSV."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(list(metrics.items()), columns=["Metric", "Value"]).to_csv(
            path, index=False
        )

    def save_report(
        self,
        ground_truth: Sequence[int],
        predictions: Sequence[int],
        path: Path = REPORT_FILE,
    ) -> None:
        """Write labelled metrics and explicit false-positive/negative counts."""
        if len(ground_truth) != len(predictions):
            raise ValueError("ground_truth and predictions must have equal length")
        metrics: dict[str, object] = self.evaluate(ground_truth, predictions)
        metrics["Total entities evaluated"] = len(ground_truth)
        metrics["False positives"] = sum(
            actual == 0 and predicted == 1
            for actual, predicted in zip(ground_truth, predictions)
        )
        metrics["False negatives"] = sum(
            actual == 1 and predicted == 0
            for actual, predicted in zip(ground_truth, predictions)
        )
        self._write_report(metrics, path)
        self.save_metrics(metrics)

    def save_detection_report(
        self,
        entity_counts: Mapping[str, int],
        total_replacements: int,
        path: Path = REPORT_FILE,
    ) -> None:
        """Write production counts and clearly mark unavailable label metrics."""
        rows: dict[str, object] = {
            "Total entities detected": int(sum(entity_counts.values())),
            "Unique replacements": int(total_replacements),
        }
        rows.update({
            f"Detected {key}": int(value)
            for key, value in sorted(entity_counts.items())
        })
        rows.update({
            "False positives": "N/A (ground truth not supplied)",
            "False negatives": "N/A (ground truth not supplied)",
            "Precision": "N/A (ground truth not supplied)",
            "Recall": "N/A (ground truth not supplied)",
            "F1 Score": "N/A (ground truth not supplied)",
            "Accuracy": "N/A (ground truth not supplied)",
        })
        self._write_report(rows, path)
        self.save_metrics(rows)

    @staticmethod
    def _write_report(rows: Mapping[str, object], path: Path) -> None:
        """Write a consistently formatted text report."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            file.write("PII Redaction Evaluation Report\n")
            file.write("=" * 34 + "\n")
            for key, value in rows.items():
                if isinstance(value, float):
                    file.write(f"{key}: {value:.4f}\n")
                else:
                    file.write(f"{key}: {value}\n")

    def print_metrics(self, metrics: Mapping[str, float]) -> None:
        """Log metrics for callers that use the original API."""
        for key, value in metrics.items():
            LOGGER.info("%-15s: %.4f", key, value)
