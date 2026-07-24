PII Redaction Tool — Submission Notes

Approach
- Hybrid: deterministic regexes for structured PII (emails, phones, IPs, SSNs, credit cards, DOBs, addresses) and spaCy/Presidio NER for PERSON and ORG.
- Conservative whitelist prevents anonymizing public institutions and legal terms.
- Deterministic Faker-based anonymization preserves repeatability via mapping.json.

Evaluation (auto-estimate)
- Candidate-level precision: 0.9149
- Candidate-level recall:    0.8776
- Candidate-level F1:        0.8958
- Occurrence-level precision: 0.6760
- Occurrence-level recall:    0.8736
- Occurrence-level F1:        0.7622
- Accuracy: 1.0000 (computed from a sampled negative document: evaluation/ground_truth_negative.json — first 5 non-empty paragraphs of input/Red_Herring_Prospectus.docx). Note: this is a small sampled negative document and may not represent corpus-wide accuracy; for authoritative accuracy, provide a larger annotated negative sample.

Notes: recall/F1 were computed with `--missed-pii 12` (an estimated missed count). For authoritative numbers, provide a manually annotated `evaluation/ground_truth.json` and/or a negative sample with true-negatives annotated.
Notes and tradeoffs
- Candidate-level metrics measure unique detector suggestions (mapping rows). Occurrence-level metrics measure actual redaction actions across the document; both are useful.
- Missed counts were estimated automatically (regex + address heuristics) and may undercount PERSON/ORG misses.
- For authoritative evaluation, annotate evaluation/ground_truth.json using evaluation/ground_truth.example.json format and run `python -m evaluation.evaluate evaluation/ground_truth.json`.

Deliverables
- Source: src/ (detector, anonymizer, utils, evaluator)
- Redacted DOCX: output/redacted_output.docx (included)
- Mapping: mapping.json (local mapping of original→fake)
- Evaluation report: output/evaluation_report.txt and output/evaluation_metrics.csv

How to reproduce
1. Install dependencies: `pip install -r requirements.txt` and `python -m spacy download en_core_web_lg`
2. Place source DOCX at input/Red_Herring_Prospectus.docx
3. Run: `python main.py`
4. Optional review CSV: `python -m evaluation.create_mapping_review` then mark `is_actual_pii` for each row, and run `python -m evaluation.review_metrics evaluation/mapping_review.csv --missed-pii N --true-negatives M` to compute final metrics.
