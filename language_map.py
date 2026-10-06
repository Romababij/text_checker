"""Language code normalisation and backend locale mapping."""

from __future__ import annotations

from typing import Optional

from lingua import Language

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
    if raw is None:
        return None
    if isinstance(raw, float) and str(raw) == "nan":
        return None
    code = str(raw).strip().upper().replace("-", "_")
    if not code:
        return None
    if code in LANG_CODE_MAP:
        return LANG_CODE_MAP[code]
    if code in LATIN_LOCALES or code in CYRILLIC_LOCALES or code in GREEK_LOCALES:
        return code
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
    mapping: dict[str, Optional[str]] = {
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
        "el_GR": None,
    }
    if locale in mapping:
        return mapping[locale]
    return None


SPELLCHECKER_AVAILABLE = frozenset({"en", "de", "fr", "es", "pt", "it", "ru"})
