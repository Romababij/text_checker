# AutoDoc Multilingual Content Validator

Streamlit app for validating multilingual automotive article content in Excel files.

## Validation layers

| Layer | Check |
|-------|--------|
| **L1** | Forbidden Unicode scripts + Cyrillic/Latin homoglyphs |
| **L2** | Target-language spelling (pyspellchecker), cross-language hits, optional Lingua mismatch |
| **L3** | US English terms in British locales (`ATD_EN`, `EN_GB`, `EN`) |

Whitelists ignore HTML/placeholders, SKUs/part numbers, and a base list of brands/OE terms (`whitelists.py` — extend as needed).

## Requirements

- Python 3.10+

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Tests

```bash
pytest tests/test_smoke.py -q
```

## Project layout

```
app.py              # Streamlit UI
validator.py        # ContentValidator (L1–L3)
language_map.py     # Language code → locale
whitelists.py       # Brands, OE terms, GB/US word lists
tests/test_smoke.py
```

## GitHub

https://github.com/Romababij/text_checker

## Accuracy limits & Hunspell path

- **pyspellchecker** ships American English, not Hunspell `en_GB`. British forms are whitelisted; US forms are flagged in L3. Proper `en_GB` coverage: add [Hunspell](https://github.com/wooorm/dictionaries) `en-GB` via `spylls` / `cyhunspell` and replace the L2 backend for `en_GB`.
- **NL, SV, PL, EL** have no bundled pyspellchecker dictionary — L2 uses cross-language detection only (weaker; more false negatives/positives).
- **Lingua** on short snippets may skip or mis-detect; L2 treats it as optional signal.
- Domain terms not in whitelist may appear as unknown words until you extend `whitelists.py` or Hunspell custom `.dic`.

Recommended upgrade: per-locale Hunspell dictionaries in `dictionaries/` and a small adapter in `validator.py` calling Hunspell when a `.dic` exists for the locale.
