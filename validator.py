"""
Multilingual content validator for AutoDoc Excel articles.

Layer 1 — Unicode script blocks + Cyrillic/Latin homoglyphs
Layer 2 — Target-language spellcheck, cross-language hits, optional Lingua mismatch
Layer 3 — US vs British English for en_GB / ATD_EN / EN
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from typing import Iterable, Optional

from bs4 import BeautifulSoup
from lingua import LanguageDetectorBuilder
from spellchecker import SpellChecker

from language_map import (
    CYRILLIC_LOCALES,
    GREEK_LOCALES,
    SPELLCHECKER_AVAILABLE,
    locale_to_lingua,
    locale_to_spellchecker_lang,
    normalize_lang_code,
)
from whitelists import (
    AUTO_WHITELIST,
    BRITISH_EXTRA_WORDS,
    US_ENGLISH_TERMS,
)

# Homoglyphs: Cyrillic letters that look like Latin (common AI corruption)
HOMOGLYPH_MAP: dict[str, str] = {
    "\u0410": "A",
    "\u0412": "B",
    "\u0415": "E",
    "\u041a": "K",
    "\u041c": "M",
    "\u041d": "H",
    "\u041e": "O",
    "\u0420": "P",
    "\u0421": "C",
    "\u0422": "T",
    "\u0423": "Y",
    "\u0425": "X",
    "\u0430": "a",
    "\u0435": "e",
    "\u043e": "o",
    "\u0440": "p",
    "\u0441": "c",
    "\u0443": "y",
    "\u0445": "x",
    "\u0456": "i",
    "\u0458": "j",
}

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


@dataclass
class RowValidationResult:
    row_index: int
    lang_code_raw: str
    locale: Optional[str]
    text: str
    l1_detail: str = ""
    l2_detail: str = ""
    l3_detail: str = ""
    flagged_tokens: list[str] = field(default_factory=list)
    error_meta: str = ""

    @property
    def is_clean(self) -> bool:
        return not (self.l1_detail or self.l2_detail or self.l3_detail or self.error_meta)

    @property
    def status(self) -> str:
        return "OK" if self.is_clean else "ISSUE"

    @property
    def status_summary(self) -> str:
        if self.is_clean:
            return "OK"
        parts = []
        if self.error_meta:
            parts.append(self.error_meta)
        if self.l1_detail:
            parts.append(f"L1: {self.l1_detail}")
        if self.l2_detail:
            parts.append(f"L2: {self.l2_detail}")
        if self.l3_detail:
            parts.append(f"L3: {self.l3_detail}")
        return " | ".join(parts)


class ContentValidator:
    LINGUA_CONFIDENCE_THRESHOLD = 0.70
    MIN_TEXT_LENGTH_FOR_LINGUA = 40
    USE_LINGUA = True

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
        return re.sub(r"\s+", " ", raw).strip()

    def _allowed_scripts_for_locale(self, locale: str) -> set[str]:
        if locale in CYRILLIC_LOCALES:
            return {"Cyrillic", "Latin"}
        if locale in GREEK_LOCALES:
            return {"Greek", "Latin"}
        return {"Latin"}

    def layer1_script_and_homoglyphs(self, text: str, locale: str) -> str:
        allowed = self._allowed_scripts_for_locale(locale)
        parts: list[str] = []

        for name, pattern in SCRIPT_PATTERNS:
            if name in allowed:
                continue
            if pattern.search(text):
                sample = pattern.findall(text)
                uniq = "".join(sorted(set(sample)))[:24]
                parts.append(f"{name} ({uniq!r})")

        homoglyphs: list[str] = []
        for char in text:
            if char in HOMOGLYPH_MAP:
                homoglyphs.append(f"{char}→{HOMOGLYPH_MAP[char]}")
        if homoglyphs:
            seen = sorted(set(homoglyphs))[:15]
            parts.append("Homoglyph: " + ", ".join(seen))

        return "; ".join(parts)

    def _is_whitelisted_token(self, token: str) -> bool:
        if token.upper() in AUTO_WHITELIST:
            return True
        if SKU_RE.match(token):
            return True
        if len(token) <= 2 and token.isalpha():
            return True
        return token.isdigit()

    def _tokenize_words(self, text: str) -> list[str]:
        return WORD_TOKEN_RE.findall(text)

    def layer2_spelling_and_lingua(
        self, text: str, locale: str
    ) -> tuple[str, list[str]]:
        sc_lang = locale_to_spellchecker_lang(locale)
        checker = self._get_spellchecker(sc_lang) if sc_lang else None
        flagged: list[str] = []

        auxiliary: list[tuple[str, SpellChecker]] = []
        for lang in ("en", "de", "fr", "es", "pt", "it", "ru"):
            if lang == sc_lang:
                continue
            aux = self._get_spellchecker(lang)
            if aux:
                auxiliary.append((lang, aux))

        for word in self._tokenize_words(text):
            if self._is_whitelisted_token(word):
                continue
            lw = word.lower()
            if locale == "en_GB" and lw in BRITISH_EXTRA_WORDS:
                continue
            if locale == "en_GB" and lw in US_ENGLISH_TERMS:
                continue

            if checker is None:
                for lang, aux in auxiliary:
                    if lw in aux:
                        flagged.append(f"{word} ({lang})")
                        break
                continue

            if lw in checker:
                continue
            if lw in checker.unknown([lw]):
                for lang, aux in auxiliary:
                    if lw in aux:
                        flagged.append(word)
                        break
                else:
                    flagged.append(word)

        unique = sorted(set(flagged), key=str.lower)[:40]
        spell_part = ", ".join(unique) if unique else ""

        lingua_part = ""
        if self.USE_LINGUA and len(text) >= self.MIN_TEXT_LENGTH_FOR_LINGUA:
            expected = locale_to_lingua(locale)
            if expected is not None:
                try:
                    confidences = self._lingua_detector.compute_language_confidence_values(
                        text
                    )
                    if confidences:
                        top = confidences[0]
                        if (
                            top.language != expected
                            and top.value >= self.LINGUA_CONFIDENCE_THRESHOLD
                        ):
                            lingua_part = (
                                f"Lingua mismatch: expected {expected.name}, "
                                f"detected {top.language.name} ({top.value:.0%})"
                            )
                except Exception:
                    pass

        if spell_part and lingua_part:
            return f"{spell_part}; {lingua_part}", unique
        if spell_part:
            return spell_part, unique
        if lingua_part:
            return lingua_part, unique
        return "", []

    def layer3_us_vs_gb(self, text: str, locale: str) -> str:
        if locale != "en_GB":
            return ""
        hits = []
        for word in self._tokenize_words(text):
            if word.lower() in US_ENGLISH_TERMS:
                hits.append(word)
        if not hits:
            return ""
        return ", ".join(sorted(set(hits), key=str.lower)[:30])

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
            result.error_meta = f"Unknown language code: {lang_str!r}"
            return result

        cleaned = self.clean_text_for_analysis(text)
        if not cleaned:
            result.error_meta = "Empty text after cleanup"
            return result

        result.l1_detail = self.layer1_script_and_homoglyphs(cleaned, locale)
        l2, flagged = self.layer2_spelling_and_lingua(cleaned, locale)
        result.l2_detail = l2
        result.flagged_tokens = flagged
        result.l3_detail = self.layer3_us_vs_gb(cleaned, locale)
        return result

    def validate_dataframe(self, df, lang_column: str, text_column: str) -> list[RowValidationResult]:
        results: list[RowValidationResult] = []
        for idx, row in df.iterrows():
            excel_row = int(idx) + 2
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
                        locale=normalize_lang_code(row.get(lang_column)),
                        text=str(row.get(text_column, "")),
                        error_meta=f"Validation error: {exc}",
                    )
                )
        return results


def build_results_table(results: Iterable[RowValidationResult]):
    import pandas as pd

    rows = []
    for r in results:
        if r.is_clean:
            continue
        rows.append(
            {
                "Row": r.row_index,
                "Language": r.lang_code_raw,
                "Locale": r.locale or "",
                "Status": r.status,
                "L1 (Script/Homoglyph)": r.l1_detail,
                "L2 (Spelling/Lingua)": r.l2_detail,
                "L3 (US vs GB)": r.l3_detail,
                "Flagged tokens": ", ".join(r.flagged_tokens),
                "Text preview": (r.text[:180] + "…") if len(r.text) > 180 else r.text,
            }
        )
    return pd.DataFrame(rows)


def build_full_export_table(results: Iterable[RowValidationResult]):
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "Row": r.row_index,
                "Language": r.lang_code_raw,
                "Locale": r.locale or "",
                "Validation_Status": r.status,
                "L1": r.l1_detail,
                "L2": r.l2_detail,
                "L3": r.l3_detail,
                "Details": r.status_summary,
            }
            for r in results
        ]
    )
