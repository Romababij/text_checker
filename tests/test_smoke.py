"""Smoke tests for ContentValidator."""

from validator import ContentValidator


def test_nl_flags_english_word():
    v = ContentValidator()
    r = v.validate_row(2, "NL", "<p>De remschijf is een replacement voor BMW.</p>")
    assert r.l2_detail
    assert "replacement" in r.l2_detail.lower()


def test_gb_flags_us_spelling():
    v = ContentValidator()
    r = v.validate_row(3, "ATD_EN", "Check your tires and center colour.")
    assert r.l3_detail
    assert "tires" in r.l3_detail.lower() or "center" in r.l3_detail.lower()


def test_de_flags_cyrillic():
    v = ContentValidator()
    r = v.validate_row(4, "DE", "Das Auto имеет проблем.")
    assert r.l1_detail
    assert "Cyrillic" in r.l1_detail


def test_homoglyph_detected():
    v = ContentValidator()
    # Cyrillic 'а' (U+0430) inside Latin word
    r = v.validate_row(5, "DE", "Brаke disc")
    assert "Homoglyph" in r.l1_detail
