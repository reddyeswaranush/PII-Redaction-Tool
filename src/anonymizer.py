"""Deterministic, entity-specific fake value generation."""

from __future__ import annotations

import logging
import random
from typing import Callable, Dict

from faker import Faker

from .config import FAKER_LOCALE, RANDOM_SEED

LOGGER = logging.getLogger(__name__)


class PIIAnonymizer:
    """Generate realistic values while preserving original-to-fake identity."""

    def __init__(self, seed: int = RANDOM_SEED, mapping: Dict[str, str] | None = None) -> None:
        """Initialize a seeded Faker instance and an optional existing mapping."""
        self.fake = Faker(FAKER_LOCALE)
        self.fake.seed_instance(seed)
        self.random = random.Random(seed)
        self.mapping: Dict[str, str] = dict(mapping or {})

    def anonymize(self, entity_type: str, value: str) -> str:
        """Return the same fake value for every occurrence of ``value``."""
        if value in self.mapping:
            return self.mapping[value]
        replacement = self._generate(entity_type)
        self.mapping[value] = replacement
        LOGGER.debug("Created replacement for %s", entity_type)
        return replacement

    def _generate(self, entity_type: str) -> str:
        """Generate a value appropriate for the normalized entity type."""
        generators: Dict[str, Callable[[], str]] = {
            "PERSON": lambda: self.fake.name(),
            "ORG": lambda: (
                f"{self.fake.first_name()} {self.fake.last_name()} "
                "Technologies Private Limited"
            ),
            "EMAIL": lambda: self.fake.email(),
            "PHONE": lambda: self._indian_phone(),
            "ADDRESS": lambda: self._indian_address(),
            "DOB": lambda: self.fake.date_of_birth(minimum_age=18, maximum_age=75).strftime("%d/%m/%Y"),
            "IP_ADDRESS": lambda: self.fake.ipv4(),
            "CREDIT_CARD": lambda: self.fake.credit_card_number(),
            "SSN": lambda: self.fake.ssn(),
        }
        generator = generators.get(entity_type)
        return generator() if generator else "<REDACTED>"

    def _indian_phone(self) -> str:
        """Return a realistic ten-digit Indian mobile number."""
        return "+91 " + str(self.random.choice([6, 7, 8, 9])) + "".join(
            str(self.random.randrange(10)) for _ in range(9)
        )

    def _indian_address(self) -> str:
        """Return a compact Indian-style address suitable for a DOCX line."""
        address = self.fake.address().replace("\n", ", ")
        return f"{address}, {self.fake.state()}, {self.fake.postcode()}, India"

    def get_mapping(self) -> Dict[str, str]:
        """Return the current original-to-fake mapping."""
        return dict(self.mapping)

    def clear_mapping(self) -> None:
        """Remove all mappings from this anonymizer."""
        self.mapping.clear()

    def total_replacements(self) -> int:
        """Return the number of unique original values replaced."""
        return len(self.mapping)
