"""CLI entry point for formatting-preserving DOCX PII redaction."""

from __future__ import annotations

from collections import Counter
import logging
from pathlib import Path
from tqdm import tqdm

from src.anonymizer import PIIAnonymizer
from src.config import INPUT_FILE, OUTPUT_FILE
from src.detector import PIIDetector
from src.evaluator import Evaluator
from src.utils import (
    create_output_directory, document_statistics, iter_document_paragraphs,
    iter_runs, load_document, load_mapping, replace_entities_in_paragraph,
    save_document, save_mapping,
)

LOGGER = logging.getLogger("pii_redaction")


def process_paragraphs(document, detector, anonymizer) -> Counter:
    """Process every paragraph in body, tables, headers, and footers."""
    counts: Counter = Counter()
    paragraphs = list(iter_document_paragraphs(document))
    for index, paragraph in enumerate(
        tqdm(paragraphs, desc="Redacting DOCX", unit="paragraph"), 1
    ):
        source = "".join(run.text or "" for run in iter_runs(paragraph))
        if not source.strip():
            continue
        entities = detector.detect(source)
        replaced = replace_entities_in_paragraph(paragraph, entities, anonymizer)
        counts.update(entity.entity_type for entity in entities)
        if index % 500 == 0:
            LOGGER.info("Processed %d/%d paragraphs; replacements=%d",
                        index, len(paragraphs), replaced)
    return counts


def process_tables(document, detector, anonymizer) -> Counter:
    """Compatibility wrapper; tables are included by ``process_paragraphs``."""
    return Counter()


def main() -> None:
    """Load, redact, evaluate the detection summary, and save the DOCX."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        create_output_directory()
        if not Path(INPUT_FILE).exists():
            raise FileNotFoundError(f"Input document not found: {INPUT_FILE}")
        LOGGER.info("Loading document: %s", INPUT_FILE)
        document = load_document(INPUT_FILE)
        LOGGER.info("Document statistics: %s", document_statistics(document))
        detector = PIIDetector()
        anonymizer = PIIAnonymizer(mapping=load_mapping())
        counts = process_paragraphs(document, detector, anonymizer)
        save_document(document, OUTPUT_FILE)
        save_mapping(anonymizer.get_mapping())
        Evaluator().save_detection_report(counts, anonymizer.total_replacements())
        LOGGER.info("Completed: %s; detected=%d, unique replacements=%d",
                    OUTPUT_FILE, sum(counts.values()), anonymizer.total_replacements())
    except Exception:
        LOGGER.exception("PII redaction failed")
        raise


if __name__ == "__main__":
    main()
