"""Conservative hybrid PII detection for long, regulation-heavy documents."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from collections import Counter
import ipaddress
import logging
import re
from typing import Iterable, List

import spacy
from presidio_analyzer import AnalyzerEngine

from .config import (
    ADDRESS_REGEX,
    ADDRESS_FIELD_REGEX,
    COMPANY_SUFFIX_REGEX,
    COMPANY_REGEX,
    CREDIT_CARD_REGEX,
    DOB_REGEX,
    EMAIL_REGEX,
    ENTITY_CONFIDENCE_THRESHOLDS,
    ENTITY_WHITELIST_NORMALIZED,
    ADDRESS_NAME_TERMS,
    ORG_PROSE_WORDS,
    PUBLIC_ORGANIZATION_WHITELIST_NORMALIZED,
    LEGAL_REFERENCE_REGEX,
    NON_PII_TERMS_NORMALIZED,
    IP_REGEX,
    PRESIDIO_LANGUAGE,
    PRESIDIO_THRESHOLD,
    PHONE_REGEX,
    SPACY_MODEL,
    SPACY_THRESHOLD,
    SSN_REGEX,
    DEFAULT_CONFIDENCE_THRESHOLD,
)

LOGGER = logging.getLogger(__name__)

# Suppress extremely high-frequency spans (likely prose/headers) that
# spaCy may label repeatedly in long regulatory documents.
FREQUENCY_SUPPRESSION_THRESHOLD = 50


@dataclass(frozen=True)
class PIIEntity:
    """A detected PII span in source text."""

    start: int
    end: int
    text: str
    entity_type: str
    score: float
    source: str = "unknown"


class PIIDetector:
    """Combine high-precision regexes with conservative NLP recognizers."""

    def __init__(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        thresholds: dict[str, float] | None = None,
    ) -> None:
        """Initialize NLP engines and per-entity confidence thresholds."""
        self.confidence_threshold = confidence_threshold
        self.thresholds = {**ENTITY_CONFIDENCE_THRESHOLDS, **(thresholds or {})}
        self.rejection_counts: Counter[str] = Counter()
        LOGGER.info("Loading spaCy model: %s", SPACY_MODEL)
        try:
            self.nlp = spacy.load(SPACY_MODEL)
        except OSError:
            LOGGER.warning("spaCy model %s is unavailable; using blank English pipeline", SPACY_MODEL)
            self.nlp = spacy.blank("en")
        LOGGER.info("Loading Presidio analyzer")
        self.presidio = AnalyzerEngine()
        LOGGER.info("PII detector ready")

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize whitespace and case for whitelist comparisons."""
        return re.sub(r"\s+", " ", value.strip()).casefold()

    def _is_public_organization(self, value: str) -> bool:
        """Return true for a protected public institution or regulator."""
        normalized = self._normalize(value)
        if normalized in PUBLIC_ORGANIZATION_WHITELIST_NORMALIZED:
            return True
        stripped = re.sub(r"^(?:the|our|this)\s+", "", normalized)
        return stripped in PUBLIC_ORGANIZATION_WHITELIST_NORMALIZED

    def _is_whitelisted(self, value: str) -> bool:
        """Return true when a value is a protected legal or regulatory term."""
        normalized = self._normalize(value)
        if (
            normalized in ENTITY_WHITELIST_NORMALIZED
            or self._is_public_organization(value)
        ):
            return True
        # Preserve common document framing without protecting arbitrary
        # company names that merely contain words such as "offer" or "issue".
        stripped = re.sub(r"^(?:the|our|this)\s+", "", normalized)
        return stripped in ENTITY_WHITELIST_NORMALIZED or bool(
            LEGAL_REFERENCE_REGEX.fullmatch(normalized)
        )

    @staticmethod
    def _span_overlaps(
        start: int,
        end: int,
        spans: tuple[tuple[int, int], ...],
    ) -> bool:
        """Return whether a candidate span overlaps a protected span."""
        return any(start < span_end and span_start < end
                   for span_start, span_end in spans)

    @staticmethod
    def _whitelist_pattern(term: str) -> re.Pattern[str]:
        """Build a case-insensitive pattern tolerant of DOCX whitespace."""
        escaped = re.escape(term).replace(r"\ ", r"\s+")
        return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)

    @lru_cache(maxsize=4096)
    def _protected_spans(self, text: str) -> tuple[tuple[int, int], ...]:
        """Find longest complete public/legal whitelist spans in ``text``."""
        terms = ENTITY_WHITELIST_NORMALIZED | PUBLIC_ORGANIZATION_WHITELIST_NORMALIZED
        matches: list[tuple[int, int]] = []
        for term in terms:
            for match in self._whitelist_pattern(term).finditer(text):
                matches.append((match.start(), match.end()))

        selected: list[tuple[int, int]] = []
        for start, end in sorted(
            set(matches),
            key=lambda span: (-(span[1] - span[0]), span[0]),
        ):
            if not self._span_overlaps(start, end, tuple(selected)):
                selected.append((start, end))
        return tuple(sorted(selected))

    def _is_blacklisted(self, value: str, source: str = "") -> bool:
        """Return true for generic nouns, headings, and legal references."""
        normalized = self._normalize(value).strip(" :;,.\/()")
        if normalized in NON_PII_TERMS_NORMALIZED:
            return True
        if LEGAL_REFERENCE_REGEX.match(normalized):
            return True
        # Uppercase section/table headings are common NER false positives.
        words = re.findall(r"[A-Za-z]+", value)
        return (
            source != "regex"
            and bool(words)
            and value.strip() == value
            and value.isupper()
            and len(words) >= 2
        )

    @staticmethod
    def _valid_ip(value: str) -> bool:
        """Validate an IPv4 candidate instead of masking numeric prose."""
        try:
            return isinstance(ipaddress.ip_address(value), ipaddress.IPv4Address)
        except ValueError:
            return False

    @staticmethod
    def _valid_card(value: str) -> bool:
        """Apply a Luhn check to credit-card candidates."""
        digits = re.sub(r"\D", "", value)
        if not 13 <= len(digits) <= 19:
            return False
        total = 0
        for index, digit in enumerate(reversed(digits)):
            number = int(digit)
            if index % 2:
                number *= 2
                if number > 9:
                    number -= 9
            total += number
        return total % 10 == 0

    def _entity(
        self, start: int, end: int, text: str, entity_type: str,
        score: float, source: str,
        protected_spans: tuple[tuple[int, int], ...] = (),
    ) -> PIIEntity | None:
        """Build an entity only when it is non-empty and not protected."""
        value = text.strip()
        if not value:
            self.rejection_counts["empty"] += 1
            return None
        if self._span_overlaps(start, end, protected_spans):
            self.rejection_counts["protected_span_skipped"] += 1
            return None
        if entity_type == "PHONE" and len(re.sub(r"\D", "", value)) < 10:
            self.rejection_counts["short_numeric_fragment"] += 1
            return None
        if entity_type in {"PERSON", "ORG", "ADDRESS"}:
            if not re.search(r"[A-Za-z]", value):
                self.rejection_counts["numeric_fragment"] += 1
                return None
            if len(value.split()) == 1 and value.isupper() and len(value) <= 5:
                self.rejection_counts["short_abbreviation"] += 1
                return None
        if self._is_public_organization(value):
            self.rejection_counts["public_organizations_skipped"] += 1
            self.rejection_counts["whitelist_hits"] += 1
            return None
        if self._is_whitelisted(value):
            self.rejection_counts["whitelist_hits"] += 1
            self.rejection_counts["whitelist"] += 1
            return None
        if self._is_blacklisted(value, source):
            self.rejection_counts["blacklist"] += 1
            return None
        return PIIEntity(start, end, value, entity_type, score, source)

    def regex_detector(
        self,
        text: str,
        protected_spans: tuple[tuple[int, int], ...] | None = None,
    ) -> List[PIIEntity]:
        """Find deterministic, high-confidence PII patterns."""
        protected_spans = protected_spans or self._protected_spans(text)
        entities: List[PIIEntity] = []
        simple_patterns = {
            "EMAIL": EMAIL_REGEX,
            "PHONE": PHONE_REGEX,
            "IP_ADDRESS": IP_REGEX,
            "SSN": SSN_REGEX,
            "CREDIT_CARD": CREDIT_CARD_REGEX,
        }
        for entity_type, pattern in simple_patterns.items():
            for match in pattern.finditer(text):
                value = match.group().strip()
                if entity_type == "IP_ADDRESS" and not self._valid_ip(value):
                    continue
                if entity_type == "CREDIT_CARD" and not self._valid_card(value):
                    continue
                entity = self._entity(match.start(), match.end(), value,
                                      entity_type, 1.0, "regex", protected_spans)
                if entity:
                    entities.append(entity)

        for match in DOB_REGEX.finditer(text):
            entity = self._entity(match.start("date"), match.end("date"),
                                  match.group("date"), "DOB", 1.0, "regex",
                                  protected_spans)
            if entity:
                entities.append(entity)

        for match in COMPANY_REGEX.finditer(text):
            raw_value = match.group("company")
            value = raw_value.strip(" ,.;:")
            start = match.start("company") + len(raw_value) - len(raw_value.lstrip())
            # Remove document framing such as "our Company" while retaining
            # the actual organization name and its legal suffix.
            parts = value.split()
            while len(parts) > 2 and parts[0].casefold().strip(" ,.:;") in {
                "our", "the", "company", "promoter", "promoters",
                "shareholder", "shareholders",
            }:
                removed = value[:len(value) - len(" ".join(parts[1:]))]
                start += len(removed)
                value = value[len(removed):].lstrip()
                parts = value.split()
            entity = self._entity(start, start + len(value), value, "ORG", 1.0,
                                  "regex", protected_spans)
            if entity and len(value.split()) >= 2:
                entities.append(entity)

        for match in ADDRESS_REGEX.finditer(text):
            value = match.group("address").strip(" \t\r\n,;:")
            start = match.start("address") + len(match.group("address")) - len(match.group("address").lstrip())
            entity = self._entity(start, start + len(value), value,
                                  "ADDRESS", 1.0, "regex", protected_spans)
            if entity:
                entities.append(entity)
        for match in ADDRESS_FIELD_REGEX.finditer(text):
            value = match.group("address").strip(" \t\r\n,;:")
            start = match.start("address") + len(match.group("address")) - len(match.group("address").lstrip())
            entity = self._entity(start, start + len(value), value,
                                  "ADDRESS", 1.0, "regex", protected_spans)
            if entity:
                entities.append(entity)
        return entities

    def spacy_detector(
        self,
        text: str,
        protected_spans: tuple[tuple[int, int], ...] | None = None,
    ) -> List[PIIEntity]:
        """Use only high-confidence PERSON and ORG NER labels.

        Generic GPE/LOC/FAC labels are deliberately excluded because legal
        prospectuses contain thousands of legitimate place names.
        """
        protected_spans = protected_spans or self._protected_spans(text)
        entities: List[PIIEntity] = []
        for ent in self.nlp(text).ents:
            entity_type = {"PERSON": "PERSON", "ORG": "ORG"}.get(ent.label_)
            if not entity_type:
                continue
            entity = self._entity(ent.start_char, ent.end_char, ent.text,
                                  entity_type, 0.90, "spacy", protected_spans)
            if entity:
                entities.append(entity)
        return entities

    def presidio_detector(
        self,
        text: str,
        protected_spans: tuple[tuple[int, int], ...] | None = None,
    ) -> List[PIIEntity]:
        """Run Presidio and retain only supported, sufficiently confident spans."""
        label_mapping = {
            "PERSON": "PERSON", "EMAIL_ADDRESS": "EMAIL",
            "PHONE_NUMBER": "PHONE", "IP_ADDRESS": "IP_ADDRESS",
            "LOCATION": "ADDRESS", "ORGANIZATION": "ORG",
            "US_SSN": "SSN", "CREDIT_CARD": "CREDIT_CARD",
        }
        protected_spans = protected_spans or self._protected_spans(text)
        entities: List[PIIEntity] = []
        for result in self.presidio.analyze(text=text, language=PRESIDIO_LANGUAGE):
            entity_type = label_mapping.get(result.entity_type)
            if not entity_type or result.score < PRESIDIO_THRESHOLD:
                continue
            value = text[result.start:result.end]
            # Presidio's generic LOCATION recognizer is too broad for this
            # corpus; accept it only beside explicit address terminology.
            if entity_type == "ADDRESS":
                context = text[max(0, result.start - 80):result.end + 80].casefold()
                if not re.search(r"registered office|corporate office|address|village|"
                                 r"taluka|district|state|pin|india", context):
                    continue
            entity = self._entity(result.start, result.end, value, entity_type,
                                  float(result.score), "presidio", protected_spans)
            if entity:
                entities.append(entity)
        return entities

    def _accepted(self, entities: Iterable[PIIEntity]) -> List[PIIEntity]:
        """Drop unsupported and low-confidence entities by source and type."""
        accepted: List[PIIEntity] = []
        for entity in entities:
            source_threshold = {
                "spacy": SPACY_THRESHOLD,
                "presidio": PRESIDIO_THRESHOLD,
            }.get(entity.source, self.confidence_threshold)
            threshold = max(source_threshold, self.confidence_threshold,
                            self.thresholds.get(entity.entity_type,
                                                 self.confidence_threshold))
            if entity.score < threshold:
                self.rejection_counts["confidence"] += 1
                continue
            if self._is_public_organization(entity.text):
                self.rejection_counts["public_organizations_skipped"] += 1
                self.rejection_counts["whitelist_hits"] += 1
                continue
            if self._is_whitelisted(entity.text):
                self.rejection_counts["whitelist_hits"] += 1
                self.rejection_counts["whitelist"] += 1
                continue
            accepted.append(entity)
        return accepted

    @staticmethod
    def _overlaps(left: PIIEntity, right: PIIEntity) -> bool:
        """Return whether two character spans overlap."""
        return left.start < right.end and right.start < left.end

    def _filter_semantic_entities(self, entities: List[PIIEntity]) -> List[PIIEntity]:
        """Apply entity-specific precision rules after confidence filtering.

        Additional heuristics:
        - Require PERSON spans to be multi-token and contain at least some
          title-cased tokens to reduce single-word or lowercase prose being
          mislabeled as persons.
        - Require ORG spans to be either compact title-cased spans or match
          a company legal suffix. Reject extremely long prose spans.
        """
        filtered: List[PIIEntity] = []
        for entity in entities:
            if entity.entity_type == "PERSON":
                role_words = {
                    "chairman",
                    "director",
                    "committee",
                    "officer",
                    "secretary",
                    "manager",
                    "promoter",
                    "shareholder",
                    "investor",
                    "auditor",
                    "registrar",
                }

                normalized = entity.text.casefold()

                if any(word in normalized for word in role_words):
                    if len(entity.text.split()) < 2:
                        continue
                words = {
                    word.casefold().strip(".,;:()")
                    for word in entity.text.split()
                }
                if words & ADDRESS_NAME_TERMS:
                    self.rejection_counts["person_address_fragment"] += 1
                    continue
                # A one-token PERSON prediction is usually a role, heading,
                # surname, or ordinary noun in this document type.
                if len(entity.text.split()) < 2 and entity.score < 0.98:
                    self.rejection_counts["person_single_word"] += 1
                    continue
                # Require some title-case evidence for multi-token PERSON spans
                tokens = [t for t in entity.text.split() if any(c.isalpha() for c in t)]
                titlecased = sum(1 for t in tokens if t[0].isupper())
                if len(tokens) >= 2 and titlecased < 1:
                    self.rejection_counts["person_not_titlecase"] += 1
                    continue
            if entity.entity_type == "ORG":
                has_company_suffix = bool(COMPANY_SUFFIX_REGEX.search(entity.text))
                words = entity.text.split()
                normalized_words = {
                    word.casefold().strip(".,;:()")
                    for word in words
                }
                prose_words = normalized_words & ORG_PROSE_WORDS
                first_word = words[0].casefold().strip(".,;:()") if words else ""

                # Reject long prose spans that happen to end in a legal
                # company suffix. A valid private company name is normally a
                # compact title-cased span.
                if has_company_suffix and (
                    first_word in ORG_PROSE_WORDS
                    or len(prose_words) >= 2
                ):
                    self.rejection_counts["org_prose_span"] += 1
                    continue
                corroborated = any(
                    other is not entity
                    and other.entity_type == "ORG"
                    and other.source != entity.source
                    and self._overlaps(entity, other)
                    for other in entities
                )
                # Regex company matches have a suffix by construction. NLP
                # organizations require either the same strong suffix or
                # high-confidence agreement between Presidio and spaCy.
                if not has_company_suffix and (
                    not corroborated
                    or len(words) < 2
                    or len(words) > 5
                ):
                    self.rejection_counts["org_weak"] += 1
                    continue
                # Require title-case for NLP-detected ORG spans to reduce
                # prose being classified as organizations in this domain.
                if not has_company_suffix:
                    titlecased = sum(1 for w in words if any(c.isalpha() for c in w) and w[0].isupper())
                    if titlecased < 1:
                        self.rejection_counts["org_not_titlecase"] += 1
                        continue
                if has_company_suffix:
                    self.rejection_counts["private_organizations_anonymized"] += 1
            filtered.append(entity)
        return filtered

    def remove_duplicates(self, entities: List[PIIEntity]) -> List[PIIEntity]:
        """Collapse identical spans, retaining the highest-confidence entity."""
        unique: dict[tuple[int, int], PIIEntity] = {}
        source_rank = {"regex": 3, "presidio": 2, "spacy": 1}
        for entity in entities:
            key = (entity.start, entity.end)
            current = unique.get(key)
            if current is None or (
                entity.score, source_rank.get(entity.source, 0)
            ) > (current.score, source_rank.get(current.source, 0)):
                unique[key] = entity
            else:
                self.rejection_counts["duplicate"] += 1
        return list(unique.values())

    def resolve_overlaps(self, entities: List[PIIEntity]) -> List[PIIEntity]:
        """Keep the highest-confidence non-overlapping spans."""
        ranked = sorted(entities, key=lambda e: (-e.score, -(e.end - e.start), e.start))
        selected: List[PIIEntity] = []
        for candidate in ranked:
            if any(candidate.start < other.end and other.start < candidate.end
                   for other in selected):
                self.rejection_counts["overlap"] += 1
                continue
            selected.append(candidate)
        return sorted(selected, key=lambda e: (e.start, e.end))

    @lru_cache(maxsize=4096)
    def _detect_cached(self, text: str) -> tuple[PIIEntity, ...]:
        """Cache exact repeated paragraph detections for large documents."""
        protected_spans = self._protected_spans(text)
        entities = self.regex_detector(text, protected_spans)
        entities.extend(self.spacy_detector(text, protected_spans))
        entities.extend(self.presidio_detector(text, protected_spans))
        clean = self._accepted(entities)
        clean = self._filter_semantic_entities(clean)
        # Frequency-based suppression: extremely frequent spans are likely
        # prose or headings rather than true entities in long regulatory
        # documents. Remove high-frequency PERSON/ORG candidates.
        frequencies = Counter(ent.text.casefold() for ent in clean)
        for ent in list(clean):
            if ent.entity_type in {"PERSON", "ORG"} and frequencies[ent.text.casefold()] > FREQUENCY_SUPPRESSION_THRESHOLD:
                # Keep only very high-confidence (>0.995) for such frequent spans
                if ent.score < 0.995:
                    self.rejection_counts["frequency_suppressed"] += 1
                    clean.remove(ent)
        result = tuple(self.resolve_overlaps(self.remove_duplicates(clean)))
        LOGGER.debug("Detection rejections so far: %s", dict(self.rejection_counts))
        return result

    def detect(self, text: str) -> List[PIIEntity]:
        """Run all recognizers once and return clean, ordered character spans."""
        if not text or not text.strip():
            return []
        return list(self._detect_cached(text))

    def print_entities(self, entities: List[PIIEntity]) -> None:
        """Log detected entities for interactive debugging."""
        for entity in entities:
            LOGGER.info("[%s] %r (%.2f, %s)", entity.entity_type, entity.text,
                        entity.score, entity.source)

    def log_rejection_summary(self) -> None:
        """Log cumulative rejection counts for detector diagnostics."""
        LOGGER.info(
            "Detector summary: public organizations skipped=%d, "
            "private organizations anonymized=%d, whitelist hits=%d, "
            "blacklist hits=%d, all rejections=%s",
            self.rejection_counts["public_organizations_skipped"],
            self.rejection_counts["private_organizations_anonymized"],
            self.rejection_counts["whitelist_hits"],
            self.rejection_counts["blacklist"],
            dict(self.rejection_counts),
        )
