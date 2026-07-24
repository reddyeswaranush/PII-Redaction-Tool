"""Central configuration for the PII redaction application."""

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
INPUT_FILE = INPUT_DIR / "Red_Herring_Prospectus.docx"
OUTPUT_FILE = OUTPUT_DIR / "redacted_output.docx"
MAPPING_FILE = BASE_DIR / "mapping.json"

SPACY_MODEL = "en_core_web_lg"
PRESIDIO_LANGUAGE = "en"
FAKER_LOCALE = "en_IN"
RANDOM_SEED = 42

SUPPORTED_ENTITIES = [
    "PERSON", "EMAIL", "PHONE", "ADDRESS", "ORG", "SSN",
    "CREDIT_CARD", "IP_ADDRESS", "DOB",
]

DEFAULT_CONFIDENCE_THRESHOLD = 0.88
SPACY_THRESHOLD = 0.92
PRESIDIO_THRESHOLD = 0.90
ENTITY_CONFIDENCE_THRESHOLDS = {
    "PERSON": 0.92, "ORG": 0.94, "ADDRESS": 0.94,
    "EMAIL": 0.95, "PHONE": 0.93, "IP_ADDRESS": 0.98,
    "SSN": 0.95, "CREDIT_CARD": 0.95, "DOB": 0.92,
}

# Protected IPO, regulatory, financial, legal, and governance vocabulary.
# These are deliberately phrase-oriented. Generic words such as "Company"
# are handled by NON_PII_TERMS so a real name ending in Limited can still be
# detected when it appears in a phrase like "our Company ABC Limited".
ENTITY_WHITELIST = {
    "SEBI", "SEBI Regulations", "Securities and Exchange Board of India",
    "BSE", "NSE", "Companies Act", "Companies (Indian Accounting Standards) Rules",
    "Red Herring Prospectus", "Prospectus", "IPO", "Initial Public Offering",
    "Offer", "Offer Price", "Offer for Sale", "Offer Documents", "Offer Proceeds",
    "Objects of the Offer", "Book Building Process", "Book Running Lead Managers",
    "Registrar", "Registrar of Companies", "Share Transfer Agents",
    "Ministry of Corporate Affairs", "Government of India", "Central Government",
    "Corporate Identity Number", "CIN", "Issue of Capital", "Issue Price",
    "Disclosure Requirements", "Qualified Institutional Buyers",
    "Retail Individual Investors", "Non-Institutional Investors",
    "Anchor Investors", "Institutional Investors", "Foreign Venture Capital Investors",
    "Reserve Bank of India", "Fresh Issue", "Bonus Issue", "Equity Share",
    "Equity Shares", "Shareholders", "Shareholder", "Investor", "Investors",
    "Risk Factors", "Financial Statements", "Financial Data", "Key Financial and Operating Metrics",
    "Adjusted EBITDA", "Non-GAAP Financial", "Allotment", "Allotted", "Allottees",
    "Application Forms", "ASBA", "ASBA Account", "ASBA Forms", "Retail Portion",
    "Public Offer Account", "Share Escrow Agent", "Promoter Group",
    "Promoter Selling Shareholders", "Individual Promoters", "Company Secretary",
    "Board of Directors", "Board/ Board of Directors", "Audit Committee",
    "CSR Committee", "Corporate Social Responsibility Committee",
    "Stakeholders Relationship Committee", "Independent Directors",
    "Independent Director", "Key Managerial Personnel", "Corporate Governance",
    "Certificate of Incorporation", "Articles of Association", "AoA/Articles of Association",
    "Financial Reporting Standards", "International Financial Reporting Standards",
    "Export Promotion Capital Goods", "Foreign Exchange Management Regulations",
    "Disclosure", "Regulatory Requirements", "Regulation S", "Schedule XIII","General Information",
    "Definitions and Abbreviations",
    "Offer Structure",
    "Offer Procedure",
    "Basis for Offer Price",
    "Summary Financial Statements",
    "Capital Structure",
    "Material Contracts",
    "Outstanding Litigation",
    "Corporate Governance",
    "Book Running Lead Managers"
}
ENTITY_WHITELIST_NORMALIZED = {term.casefold() for term in ENTITY_WHITELIST}

# Public institutions and regulatory bodies must never be anonymized, even
# when a detector labels them as ORG, PERSON, or another supported type.
PUBLIC_ORGANIZATION_WHITELIST = {
    "SEBI",
    "Securities and Exchange Board of India",
    "BSE",
    "BSE Limited",
    "National Stock Exchange",
    "National Stock Exchange of India Limited",
    "NSE",
    "Registrar of Companies",
    "RoC",
    "Ministry of Corporate Affairs",
    "MCA",
    "Government of India",
    "Reserve Bank of India",
    "RBI",
    "Income Tax Department",
    "GST Council",
    "Central Electricity Authority",
    "Central Electricity Regulatory Commission",
    "Export Import Bank of India",
    "ICAI",
    "Indian Accounting Standards",
    "Companies Act",
    "SEBI ICDR Regulations",
    "Foreign Exchange Management Act",
    "Securities Contracts (Regulation) Act",
}
PUBLIC_ORGANIZATION_WHITELIST_NORMALIZED = {
    organization.casefold()
    for organization in PUBLIC_ORGANIZATION_WHITELIST
}

# Generic nouns and headings that spaCy/Presidio frequently label as ORG or
# PERSON in prospectuses. Matching is exact after normalization.
NON_PII_TERMS = {
    "board", "board of directors", "company", "companies", "committee",
    "chairman", "managing director", "director", "directors", "promoter",
    "promoters", "employee", "employees", "investor", "investors",
    "shareholder", "shareholders", "issuer", "registrar", "regulator",
    "issue", "offer", "offer price", "equity share", "equity shares",
    "prospectus", "risk factors", "financial statements", "financial data",
    "section", "chapter", "schedule", "rule", "regulation", "appendix",
    "annexure", "table", "contents", "notes", " auditors", "auditor",
    "banker", "bankers", "manager", "managers", "buyers", "retail investors",
    "book building process", "book running lead managers", "qualified institutional buyers",
    "retail individual investors", "non-institutional investors","general information",
    "definitions",
    "abbreviations",
    "summary",
    "summary financial statements",
    "offer structure",
    "book running lead managers",
    "book building process",
    "offer document",
    "offer documents",
    "offer procedure",
    "offer period",
    "bid",
    "bidders",
    "anchor investor",
    "anchor investors",
    "qualified institutional buyers",
    "retail portion",
    "non-institutional portion",
    "qib","issuer","listing","initial public offering","red herring prospectus","companies act","companies act 2013","risk factors","our company","corporate office","registered office","contact person",
}
NON_PII_TERMS_NORMALIZED = {term.casefold() for term in NON_PII_TERMS}

# Words that indicate an NER span is document prose rather than a company
# name. These prevent long clauses from being anonymized as one organization.
ORG_PROSE_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "being", "by", "for",
    "from", "in", "including", "namely", "of", "on", "or", "our", "pursuant",
    "the", "their", "this", "to", "was", "were", "with", "whom",
}

ADDRESS_NAME_TERMS = {
    "apartment", "colony", "complex", "court", "floor", "garden",
    "house", "lane", "marg", "nagar", "park", "pune", "road", "society",
    "street", "tower", "village",
}

COMPANY_SUFFIX_REGEX = re.compile(
    r"(?i)(?:private\s+limited|pvt\.?\s+ltd\.?|limited|ltd\.?|llp|inc\.?|corporation)\s*$"
)
LEGAL_REFERENCE_REGEX = re.compile(
    r"(?i)^(?:section|chapter|schedule|rule|regulation|article|clause)\b"
)

EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_REGEX = re.compile(
    r"(?<!\d)(?:\+91[\s.-]?)?(?:[6-9]\d{4}[\s.-]?\d{5}|[6-9]\d{9})(?!\d)"
)
IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_REGEX = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
DOB_REGEX = re.compile(
    r"(?i)\b(?:date\s+of\s+birth|dob|born\s+on)\s*[:\-]?\s*"
    r"(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"
)
COMPANY_REGEX = re.compile(
    r"(?<![A-Za-z])(?P<company>(?:[A-Z][A-Za-z0-9&.'()/\-]*\s+){1,5}"
    r"(?:Private\s+Limited|Pvt\.?\s+Ltd\.?|Limited|Ltd\.?|LLP|"
    r"Inc\.?|Corporation))\b",
)
ADDRESS_REGEX = re.compile(
    r"(?ims)\b(?:Registered\s+Office|Corporate\s+Office|Branch\s+Office|"
    r"Correspondence\s+Address|Residential\s+Address)\s*[:\-]?\s*"
    r"(?P<address>[^;]{2,300}?"
    r"(?:(?:\bVillage\b|\bTaluka\b|\bDistrict\b|\bState\b|"
    r"\bPIN(?:\s*Code)?\b|\bIndia\b)[^;]{0,180}))(?=;|\n\s*\n|$)"
)
ADDRESS_FIELD_REGEX = re.compile(
    r"(?im)\b(?:Village|Taluka|District|State|PIN(?:\s*Code)?)\s*[:\-]\s*"
    r"(?P<address>[^\r\n;]{2,120})"
)
INDIAN_PIN_REGEX = re.compile(r"\b[1-9]\d{5}\b")

METRICS_FILE = OUTPUT_DIR / "evaluation_metrics.csv"
REPORT_FILE = OUTPUT_DIR / "evaluation_report.txt"
