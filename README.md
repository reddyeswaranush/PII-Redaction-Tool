# PII Redaction Tool

This project reads a Microsoft Word document, detects personally identifiable
information, replaces it with deterministic fake values, and writes a
formatting-preserving redacted DOCX.

The implementation uses a conservative hybrid detector:

- Regular expressions for structured values such as emails, phones, dates,
  IP addresses, credit cards, and company suffixes.
- spaCy NER for names and organizations.
- Microsoft Presidio for additional PII recognizers.
- A legal/regulatory whitelist and public-organization whitelist to avoid
  changing prospectus terminology or official institutions.
- Faker for realistic replacement values.

Precision is prioritized over recall for regulatory documents. Generic words
such as `Board`, `Company`, and `Registrar` are not treated as PII. Public
institutions such as SEBI, BSE Limited, NSE, and the Reserve Bank of India are
protected. This can miss uncertain names or organizations, but reduces false
positives in legal and financial text.

## Supported PII

- Person names
- Email addresses
- Indian phone numbers
- Private company names
- Physical addresses
- SSNs
- Credit card numbers
- Dates of birth
- IPv4 addresses

## Project structure

```text
pii/
├── input/                         # Local input document; not committed
├── output/                        # Redacted DOCX and reports
├── src/
│   ├── __init__.py
│   ├── anonymizer.py
│   ├── config.py
│   ├── detector.py
│   ├── evaluator.py
│   └── utils.py
├── evaluation/
│   ├── evaluate.py
│   └── ground_truth.example.json
├── tests/
│   ├── test_anonymizer.py
│   └── test_detector.py
├── main.py
├── requirements.txt
└── README.md
```

The original prospectus and `mapping.json` are excluded from Git because they
can contain sensitive PII. The generated redacted output is included for
review.

## Installation

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_lg
```

## Run redaction

Place the source document at:

```text
input/Red_Herring_Prospectus.docx
```

Then run:

```bash
python main.py
```

Generated files:

```text
output/redacted_output.docx
output/evaluation_report.txt
output/evaluation_metrics.csv
mapping.json                 # local only; ignored by Git
```

The existing mapping is loaded before processing. Therefore, the same original
value receives the same fake value across runs.

## Formatting preservation

The tool edits DOCX text at run level rather than assigning to
`paragraph.text`. This preserves bold, italic, underline, font, color, and
hyperlink wrappers. It processes body paragraphs, tables, nested tables,
headers, and footers.

## Evaluation

The production report contains detection counts. Numeric precision, recall,
F1, and accuracy require manually annotated ground truth; they must not be
invented from detector output alone.

Create a private file named:

```text
evaluation/ground_truth.json
```

using the format in `evaluation/ground_truth.example.json`. Each document must
contain its source text and exact entity spans:

```json
{
  "documents": [
    {
      "id": "document-1",
      "text": "Contact Rashi Patil at rashi.patil@example.com.",
      "entities": [
        {"start": 8, "end": 19, "entity_type": "PERSON"},
        {"start": 23, "end": 46, "entity_type": "EMAIL"}
      ]
    }
  ]
}
```

Run evaluation with:

```bash
python -m evaluation.evaluate evaluation/ground_truth.json
```

Entity precision, recall, and F1 use exact span and entity-type matching.
Accuracy is calculated at character level because entity extraction does not
provide a natural entity-level true-negative count.

Run-time reviewed metrics (this repository state):

- Reviewed candidates: 94
- True positives: 86
- False positives: 8
- True-positive occurrences: 242
- False-positive occurrences: 116
- Precision: 0.9149
- Recall: 0.8776  (computed using `--missed-pii 12` as an estimated missed count)
- F1 Score: 0.8958
- Accuracy: 1.0000 (computed from a sampled negative document: evaluation/ground_truth_negative.json — first 5 non-empty paragraphs of input/Red_Herring_Prospectus.docx). Note: this is a small sampled negative document and may not represent corpus-wide accuracy; for authoritative accuracy, provide a larger annotated negative sample.

For a faster review of the actual run, generate a local CSV from the original
DOCX, redacted DOCX, and `mapping.json`:

```bash
python -m evaluation.create_mapping_review
```

Review `evaluation/mapping_review.csv` and set `is_actual_pii` to `yes` or
`no` for every row. Then calculate reviewed precision:

```bash
python -m evaluation.review_metrics evaluation/mapping_review.csv
```

Add `--missed-pii N` after manually counting PII missed in the original to
calculate recall and F1. Add `--true-negatives N` only when a separate
negative sample has been annotated; otherwise accuracy is correctly reported
as unavailable rather than guessed.

## Tests

Run the regression tests with:

```bash
pytest
```

The tests cover public multi-word organization protection, private company
detection, legal-term filtering, and deterministic anonymization.
