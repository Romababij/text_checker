"""Smoke tests for ContentValidator."""

from validator import ContentValidator, IssueType


def test_nl_flags_english_word():
    v = ContentValidator()
    r = v.validate_row(2, "NL", "<p>De remschijf is een replacement voor BMW.</p>")
    types = {i.issue_type for i in r.issues}
    assert IssueType.FOREIGN_WORD in types


def test_gb_flags_us_spelling():
    v = ContentValidator()
    r = v.validate_row(3, "ATD_EN", "Check your tires and center colour.")
    types = {i.issue_type for i in r.issues}
    assert IssueType.US_ENGLISH_IN_GB in types


def test_de_flags_cyrillic():
    v = ContentValidator()
    r = v.validate_row(4, "DE", "Das Auto имеет проблем.")
    types = {i.issue_type for i in r.issues}
    assert IssueType.FOREIGN_SCRIPT in types
