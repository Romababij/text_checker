"""
AutoDoc multilingual Excel content validator — Streamlit UI.
"""

from __future__ import annotations

import io
from typing import Optional

import pandas as pd
import streamlit as st
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

from validator import ContentValidator, RowValidationResult, build_results_table

st.set_page_config(
    page_title="AutoDoc Content Validator",
    page_icon="🛡️",
    layout="wide",
)

PROBLEM_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")


@st.cache_resource
def get_validator() -> ContentValidator:
    return ContentValidator()


def export_validated_excel(
    df: pd.DataFrame,
    results: list[RowValidationResult],
    lang_column: str,
    text_column: str,
) -> bytes:
    out_df = df.copy()
    status_by_row = {r.row_index: "OK" if r.is_clean else r.status_summary for r in results}
    # pandas index -> excel row
    statuses = []
    for idx in df.index:
        excel_row = int(idx) + 2
        statuses.append(status_by_row.get(excel_row, "OK"))
    out_df["Validation_Status"] = statuses

    buffer = io.BytesIO()
    out_df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    wb = load_workbook(buffer)
    ws = wb.active
    headers = [cell.value for cell in ws[1]]
    try:
        text_col_idx = headers.index(text_column) + 1
    except ValueError:
        text_col_idx = None

    problem_rows = {r.row_index for r in results if not r.is_clean}
    if text_col_idx is not None:
        for excel_row in problem_rows:
            ws.cell(row=excel_row, column=text_col_idx).fill = PROBLEM_FILL

    out_buffer = io.BytesIO()
    wb.save(out_buffer)
    return out_buffer.getvalue()


def main() -> None:
    st.title("🛡️ AutoDoc — Multilingual Content Validator")
    st.markdown(
        "Upload an Excel file with language codes and article text. "
        "The tool runs **script**, **dictionary**, and **Lingua** checks."
    )

    uploaded = st.file_uploader("Excel file (.xlsx)", type=["xlsx"])

    if uploaded is None:
        st.info("Upload a `.xlsx` file to begin.")
        return

    try:
        df = pd.read_excel(uploaded, engine="openpyxl")
    except Exception as exc:
        st.error(f"Could not read Excel file: {exc}")
        return

    if df.empty:
        st.warning("The file has no data rows.")
        return

    columns = list(df.columns.astype(str))
    col1, col2 = st.columns(2)
    with col1:
        lang_column = st.selectbox("Language code column", columns, index=0)
    with col2:
        default_text_idx = min(1, len(columns) - 1)
        text_column = st.selectbox("Article text column", columns, index=default_text_idx)

    if st.button("Run validation", type="primary"):
        with st.spinner("Validating…"):
            validator = get_validator()
            results = validator.validate_dataframe(df, lang_column, text_column)
        st.session_state["validation_results"] = results
        st.session_state["validation_df"] = df
        st.session_state["lang_column"] = lang_column
        st.session_state["text_column"] = text_column

    results: Optional[list[RowValidationResult]] = st.session_state.get("validation_results")
    if not results:
        st.caption(f"Loaded **{len(df)}** rows. Choose columns and run validation.")
        return

    total = len(results)
    clean = sum(1 for r in results if r.is_clean)
    problems = total - clean

    m1, m2, m3 = st.columns(3)
    m1.metric("Total rows", total)
    m2.metric("Clean rows", clean)
    m3.metric("Problem rows", problems)

    problem_df = build_results_table(results)
    all_issue_types = sorted({i.issue_type.value for r in results for i in r.issues})
    all_langs = sorted({r.lang_code_raw for r in results if not r.is_clean})

    f1, f2 = st.columns(2)
    with f1:
        filter_issue = st.multiselect(
            "Filter by issue type",
            all_issue_types,
            default=[],
        )
    with f2:
        filter_lang = st.multiselect(
            "Filter by language code",
            all_langs,
            default=[],
        )

    filtered = problem_df
    if not problem_df.empty:
        if filter_issue:
            mask = problem_df["Issue Types"].apply(
                lambda s: any(t in str(s) for t in filter_issue)
            )
            filtered = filtered[mask]
        if filter_lang:
            filtered = filtered[filtered["Language Code"].isin(filter_lang)]

    st.subheader("Problem rows")
    if filtered.empty:
        st.success("No problem rows match the current filters." if problems == 0 else "No rows match filters.")
    else:
        st.dataframe(filtered, use_container_width=True, hide_index=True)

    st.subheader("Export")
    df_export = st.session_state.get("validation_df", df)
    lang_col = st.session_state.get("lang_column", lang_column)
    text_col = st.session_state.get("text_column", text_column)
    try:
        xlsx_bytes = export_validated_excel(df_export, results, lang_col, text_col)
        st.download_button(
            label="Download validated_articles.xlsx",
            data=xlsx_bytes,
            file_name="validated_articles.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as exc:
        st.error(f"Export failed: {exc}")

    with st.expander("Validation layers (reference)"):
        st.markdown(
            """
            1. **Unicode / script** — forbidden scripts for Latin locales (Cyrillic, CJK, etc.).
            2. **Dictionary** — words must match target language (pyspellchecker + whitelist).
            3. **Lingua** — document-level language mismatch if confidence ≥ 70%.
            """
        )


if __name__ == "__main__":
    main()
