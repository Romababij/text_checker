"""
Multilingual content validator for AutoDoc Excel articles.
Three layers: script filter, dictionary check, language detection (Lingua).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from html import unescape
from typing import Iterable, Optional

from bs4 import BeautifulSoup
from lingua import Language, LanguageDetectorBuilder
from spellchecker import SpellChecker

# ---------------------------------------------------------------------------
# Language mapping
# ---------------------------------------------------------------------------

LATIN_LOCALES = frozenset(
    {
        "en_GB",
        "de_DE",
        "nl_NL",
        "fr_FR",
        "es_ES",
        "pt_PT",
        "sv_SE",
        "pl_PL",
        "it_IT",
        "da_DK",
        "fi_FI",
        "ro_RO",
        "cs_CZ",
        "hu_HU",
    }
)

CYRILLIC_LOCALES = frozenset({"uk_UA", "bg_BG", "ru_RU"})
GREEK_LOCALES = frozenset({"el_GR"})

# Raw code -> normalized locale key
LANG_CODE_MAP: dict[str, str] = {
    "ATD_EN": "en_GB",
    "EN_GB": "en_GB",
    "EN-GB": "en_GB",
    "GB": "en_GB",
    "EN": "en_GB",
    "UK_EN": "en_GB",
    "DE": "de_DE",
    "DE_DE": "de_DE",
    "NL": "nl_NL",
    "NL_NL": "nl_NL",
    "FR": "fr_FR",
    "FR_FR": "fr_FR",
    "ES": "es_ES",
    "ES_ES": "es_ES",
    "PT": "pt_PT",
    "PT_PT": "pt_PT",
    "SE": "sv_SE",
    "SV": "sv_SE",
    "SV_SE": "sv_SE",
    "PL": "pl_PL",
    "PL_PL": "pl_PL",
    "EL": "el_GR",
    "GR": "el_GR",
    "EL_GR": "el_GR",
    "BG": "bg_BG",
    "BG_BG": "bg_BG",
    "UK": "uk_UA",
    "UA": "uk_UA",
    "UK_UA": "uk_UA",
    "IT": "it_IT",
    "IT_IT": "it_IT",
}


def normalize_lang_code(raw: object) -> Optional[str]:
    if raw is None or (isinstance(raw, float) and str(raw) == "nan"):
        return None
    code = str(raw).strip().upper().replace("-", "_")
    if not code:
        return None
    if code in LANG_CODE_MAP:
        return LANG_CODE_MAP[code]
    if code in LATIN_LOCALES or code in CYRILLIC_LOCALES or code in GREEK_LOCALES:
        return code
    # Short codes like EN_GB already handled; try prefix match
    for key, locale in LANG_CODE_MAP.items():
        if key == code:
            return locale
    return None


def locale_to_lingua(locale: str) -> Optional[Language]:
    mapping = {
        "en_GB": Language.ENGLISH,
        "de_DE": Language.GERMAN,
        "nl_NL": Language.DUTCH,
        "fr_FR": Language.FRENCH,
        "es_ES": Language.SPANISH,
        "pt_PT": Language.PORTUGUESE,
        "sv_SE": Language.SWEDISH,
        "pl_PL": Language.POLISH,
        "el_GR": Language.GREEK,
        "bg_BG": Language.BULGARIAN,
        "uk_UA": Language.UKRAINIAN,
        "it_IT": Language.ITALIAN,
    }
    return mapping.get(locale)


def locale_to_spellchecker_lang(locale: str) -> Optional[str]:
    """pyspellchecker language codes (limited set)."""
    mapping = {
        "en_GB": "en",
        "de_DE": "de",
        "fr_FR": "fr",
        "es_ES": "es",
        "pt_PT": "pt",
        "it_IT": "it",
        "pl_PL": None,
        "nl_NL": None,
        "sv_SE": None,
        "uk_UA": "ru",
        "bg_BG": "ru",
    }
    lang = mapping.get(locale)
    if lang is None and locale not in mapping:
        return None
    return lang


# pyspellchecker actually supports: en, es, de, fr, pt, it, ru, lv, eu — not nl, pl, sv
SPELLCHECKER_AVAILABLE = frozenset({"en", "de", "fr", "es", "pt", "it", "ru"})

# ---------------------------------------------------------------------------
# Whitelists & British English
# ---------------------------------------------------------------------------

AUTO_WHITELIST = frozenset(
    w.upper()
    for w in (
        "BMW",
        "VW",
        "Audi",
        "Mercedes",
        "Mercedes-Benz",
        "Opel",
        "ABS",
        "ESP",
        "VIN",
        "OEN",
        "OEM",
        "KW",
        "HP",
        "TDI",
        "CDTI",
        "ISOFIX",
        "LED",
        "DOT4",
        "AutoDoc",
        "Autodoc",
        "VAG",
        "VW",
        "SEAT",
        "Skoda",
        "Škoda",
        "Ford",
        "Toyota",
        "Renault",
        "Peugeot",
        "Citroën",
        "Citroen",
        "Volvo",
        "Saab",
        "Fiat",
        "Alfa",
        "Romeo",
        "Porsche",
        "Mini",
        "Nissan",
        "Honda",
        "Hyundai",
        "Kia",
        "Mazda",
        "Subaru",
        "Suzuki",
        "Dacia",
        "Jeep",
        "Land",
        "Rover",
        "Jaguar",
        "Tesla",
        "MAN",
        "DAF",
        "Iveco",
        "Scania",
        "EGR",
        "DPF",
        "OBD",
        "CAN",
        "ECU",
        "ASR",
        "TCS",
        "ACC",
        "GPS",
        "USB",
        "OBD2",
        "HTML",
        "PDF",
    )
)

BRITISH_EXTRA_WORDS = frozenset(
    w.lower()
    for w in (
        "tyres",
        "tyre",
        "enquiry",
        "enquiries",
        "centre",
        "centres",
        "colour",
        "colours",
        "catalogue",
        "catalogues",
        "brake",
        "disc",
        "discs",
        "favour",
        "favourite",
        "honour",
        "labour",
        "organise",
        "organised",
        "recognise",
        "metre",
        "litre",
        "programme",
        "defence",
        "licence",
        "practise",
        "analyse",
        "aluminium",
        "behaviour",
        "neighbour",
        "travelling",
        "cancelled",
        "modelling",
    )
)

US_ENGLISH_TERMS = frozenset(
    w.lower()
    for w in (
        "tires",
        "tire",
        "inquiry",
        "inquiries",
        "center",
        "centers",
        "color",
        "colors",
        "catalog",
        "catalogs",
        "defense",
        "license",
        "organize",
        "organized",
        "recognize",
        "meter",
        "liter",
        "program",
        "analyze",
        "aluminum",
        "behavior",
        "neighbor",
        "traveling",
        "canceled",
        "modeling",
        "favorite",
        "honor",
        "labor",
        "favor",
    )
)

# Script regex blocks (forbidden in Latin texts)
SCRIPT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Cyrillic", re.compile(r"[\u0400-\u04FF]")),
    ("Greek", re.compile(r"[\u0370-\u03FF]")),
    ("Devanagari", re.compile(r"[\u0900-\u097F]")),
    ("CJK", re.compile(r"[\u4E00-\u9FFF]")),
    ("Arabic", re.compile(r"[\u0600-\u06FF]")),
]

WORD_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+(?:[''-][A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+)*")
SKU_RE = re.compile(
    r"^(?:\d+[A-Za-z][A-Za-z0-9]*|[A-Za-z]+\d+[A-Za-z0-9]*|\d+[Vv]|R\d{1,2}|"
    r"\d{1,2}[Ww]\d{1,2}|[0-9]+(?:[.,][0-9]+)?)$"
)
PLACEHOLDER_RE = re.compile(r"\{[^}]+\}|%[sd]|%\(\w+\)[sd]")
HTML_ENTITY_RE = re.compile(r"&(?:nbsp|amp|lt|gt|quot|#\d+);", re.I)


class IssueType(str, Enum):
    FOREIGN_SCRIPT = "Foreign Script"
    FOREIGN_WORD = "Foreign / Unknown Word"
    US_ENGLISH_IN_GB = "US English term (expected British)"
    LANGUAGE_MISMATCH = "Language Mismatch"
    EMPTY_TEXT = "Empty Text"
    UNKNOWN_LANG = "Unknown Language Code"


@dataclass
class ValidationIssue:
    issue_type: IssueType
    detail: str


@dataclass
class RowValidationResult:
    row_index: int
    lang_code_raw: str
    locale: Optional[str]
    text: str
    issues: list[ValidationIssue] = field(default_factory=list)
    flagged_tokens: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.issues) == 0

    @property
    def status_summary(self) -> str:
        if self.is_clean:
            return "OK"
        parts = [f"{i.issue_type.value}: {i.detail}" for i in self.issues]
        return " | ".join(parts)


class ContentValidator:
    LINGUA_CONFIDENCE_THRESHOLD = 0.70
    MIN_TEXT_LENGTH_FOR_LINGUA = 40

    def __init__(self) -> None:
        self._spell_checkers: dict[str, SpellChecker] = {}
        self._lingua_detector = LanguageDetectorBuilder.from_all_languages().build()

    def _get_spellchecker(self, lang: str) -> Optional[SpellChecker]:
        if lang not in SPELLCHECKER_AVAILABLE:
            return None
        if lang not in self._spell_checkers:
            self._spell_checkers[lang] = SpellChecker(language=lang)
        return self._spell_checkers[lang]

    def clean_text_for_analysis(self, text: str) -> str:
        if not text or not str(text).strip():
            return ""
        raw = str(text)
        raw = PLACEHOLDER_RE.sub(" ", raw)
        raw = HTML_ENTITY_RE.sub(" ", raw)
        try:
            soup = BeautifulSoup(raw, "html.parser")
            raw = soup.get_text(separator=" ")
        except Exception:
            raw = re.sub(r"<[^>]+>", " ", raw)
        raw = unescape(raw)
        raw = re.sub(r"\s+", " ", raw).strip()
        return raw

    def _allowed_scripts_for_locale(self, locale: str) -> set[str]:
        if locale in CYRILLIC_LOCALES:
            return {"Cyrillic", "Latin"}  # mixed Latin brands OK
        if locale in GREEK_LOCALES:
            return {"Greek", "Latin"}
        return {"Latin"}

    def check_foreign_scripts(self, text: str, locale: str) -> list[ValidationIssue]:
        allowed = self._allowed_scripts_for_locale(locale)
        found: list[str] = []
        for name, pattern in SCRIPT_PATTERNS:
            if name in allowed:
                continue
            matches = pattern.findall(text)
            if matches:
                sample = "".join(sorted(set(matches)))[:20]
                found.append(f"{name} ({sample!r})")
        if not found:
            return []
        return [
            ValidationIssue(
                IssueType.FOREIGN_SCRIPT,
                "; ".join(found),
            )
        ]

    def _is_whitelisted_token(self, token: str) -> bool:
        upper = token.upper()
        if upper in AUTO_WHITELIST:
            return True
        if SKU_RE.match(token):
            return True
        if len(token) <= 2 and token.isalpha():
            return True
        if token.isdigit():
            return True
        return False

    def _tokenize_words(self, text: str) -> list[str]:
        return WORD_TOKEN_RE.findall(text)

    def check_us_english_in_gb(self, text: str, locale: str) -> list[ValidationIssue]:
        if locale != "en_GB":
            return []
        hits = []
        for word in self._tokenize_words(text):
            lw = word.lower()
            if lw in US_ENGLISH_TERMS:
                hits.append(word)
        if not hits:
            return []
        unique = sorted(set(hits), key=str.lower)
        return [
            ValidationIssue(
                IssueType.US_ENGLISH_IN_GB,
                ", ".join(unique[:30]),
            )
        ]

    def check_dictionary(
        self, text: str, locale: str
    ) -> tuple[list[ValidationIssue], list[str]]:
        sc_lang = locale_to_spellchecker_lang(locale)
        checker = self._get_spellchecker(sc_lang) if sc_lang else None

        foreign_or_unknown: list[str] = []
        auxiliary_checkers: list[tuple[str, SpellChecker]] = []
        for lang in ("en", "de", "fr", "es", "pt", "it"):
            if lang == sc_lang:
                continue
            aux = self._get_spellchecker(lang)
            if aux:
                auxiliary_checkers.append((lang, aux))

        for word in self._tokenize_words(text):
            if self._is_whitelisted_token(word):
                continue
            lw = word.lower()
            if locale == "en_GB" and lw in BRITISH_EXTRA_WORDS:
                continue
            if locale == "en_GB" and lw in US_ENGLISH_TERMS:
                continue

            if checker is None:
                # No target dictionary: flag if strongly matches another language
                for lang, aux in auxiliary_checkers:
                    if lw in aux:
                        foreign_or_unknown.append(f"{word} ({lang})")
                        break
                continue

            if lw in checker:
                continue
            if lw in checker.unknown([lw]):
                # unknown in target — foreign if known elsewhere
                for lang, aux in auxiliary_checkers:
                    if lw in aux:
                        foreign_or_unknown.append(word)
                        break
                else:
                    foreign_or_unknown.append(word)

        if not foreign_or_unknown:
            return [], []
        unique = sorted(set(foreign_or_unknown), key=str.lower)
        return [
            ValidationIssue(
                IssueType.FOREIGN_WORD,
                ", ".join(unique[:40]),
            )
        ], unique[:40]

    def check_lingua_mismatch(self, text: str, locale: str) -> list[ValidationIssue]:
        if len(text) < self.MIN_TEXT_LENGTH_FOR_LINGUA:
            return []
        expected = locale_to_lingua(locale)
        if expected is None:
            return []
        try:
            confidences = self._lingua_detector.compute_language_confidence_values(text)
        except Exception:
            return []
        if not confidences:
            return []
        top = confidences[0]
        if top.language == expected:
            return []
        if top.value < self.LINGUA_CONFIDENCE_THRESHOLD:
            return []
        return [
            ValidationIssue(
                IssueType.LANGUAGE_MISMATCH,
                f"expected {expected.name}, detected {top.language.name} ({top.value:.0%})",
            )
        ]

    def validate_row(
        self,
        row_index: int,
        lang_raw: object,
        text_raw: object,
    ) -> RowValidationResult:
        lang_str = "" if lang_raw is None else str(lang_raw).strip()
        text = "" if text_raw is None else str(text_raw)

        locale = normalize_lang_code(lang_raw)
        result = RowValidationResult(
            row_index=row_index,
            lang_code_raw=lang_str,
            locale=locale,
            text=text,
        )

        if locale is None:
            result.issues.append(
                ValidationIssue(
                    IssueType.UNKNOWN_LANG,
                    f"Unmapped language code: {lang_str!r}",
                )
            )
            return result

        cleaned = self.clean_text_for_analysis(text)
        if not cleaned:
            result.issues.append(
                ValidationIssue(IssueType.EMPTY_TEXT, "No analysable text after cleanup")
            )
            return result

        result.issues.extend(self.check_foreign_scripts(cleaned, locale))
        result.issues.extend(self.check_us_english_in_gb(cleaned, locale))
        dict_issues, flagged = self.check_dictionary(cleaned, locale)
        result.issues.extend(dict_issues)
        result.flagged_tokens.extend(flagged)
        result.issues.extend(self.check_lingua_mismatch(cleaned, locale))

        return result

    def validate_dataframe(
        self,
        df,
        lang_column: str,
        text_column: str,
    ) -> list[RowValidationResult]:
        results: list[RowValidationResult] = []
        for idx, row in df.iterrows():
            excel_row = int(idx) + 2  # header + 1-based
            try:
                results.append(
                    self.validate_row(
                        excel_row,
                        row.get(lang_column),
                        row.get(text_column),
                    )
                )
            except Exception as exc:
                results.append(
                    RowValidationResult(
                        row_index=excel_row,
                        lang_code_raw=str(row.get(lang_column, "")),
                        locale=None,
                        text=str(row.get(text_column, "")),
                        issues=[
                            ValidationIssue(
                                IssueType.FOREIGN_WORD,
                                f"Validation error: {exc}",
                            )
                        ],
                    )
                )
        return results


def build_results_table(results: Iterable[RowValidationResult]):
    import pandas as pd

    rows = []
    for r in results:
        if r.is_clean:
            continue
        issue_types = ", ".join(sorted({i.issue_type.value for i in r.issues}))
        rows.append(
            {
                "Row": r.row_index,
                "Language Code": r.lang_code_raw,
                "Locale": r.locale or "",
                "Issue Types": issue_types,
                "Details": r.status_summary,
                "Flagged Words/Symbols": ", ".join(r.flagged_tokens),
                "Text Preview": (r.text[:200] + "…") if len(r.text) > 200 else r.text,
            }
        )
    return pd.DataFrame(rows)
