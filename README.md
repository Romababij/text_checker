# AutoDoc Multilingual Content Validator

Local Streamlit app for validating multilingual article content in Excel files (AutoDoc content pipeline).

## Features

- **Level 1:** Foreign script detection (Cyrillic, Greek, CJK, Arabic, Devanagari) for Latin locales
- **Level 2:** Spellcheck-based foreign/unknown word detection with automotive whitelist
- **Level 3:** Lingua language mismatch detection on longer texts
- **British English (`EN_GB` / `ATD_EN`):** flags US spellings (`tires`, `center`, …)
- **Export:** `validated_articles.xlsx` with `Validation_Status` and pink highlight on problem text cells

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Open the URL shown in the terminal (usually http://localhost:8501).

## Excel format

Your file should include at least:

- A column with language codes (`DE`, `NL`, `ATD_EN`, `FR`, …)
- A column with HTML or plain article text

Select those columns in the UI after upload.

## Notes

- Unknown language codes are reported as issues and skipped for deep checks.
- Empty cells are marked as **Empty Text**.
- Dictionary coverage follows `pyspellchecker` languages (EN, DE, FR, ES, PT, IT, RU). For locales without a bundled dictionary (e.g. NL, SV), foreign words are inferred when they match another loaded dictionary.
