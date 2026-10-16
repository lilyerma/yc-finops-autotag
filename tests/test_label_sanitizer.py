"""Unit tests for label_sanitizer.py — pure string logic, no cloud deps."""
from label_sanitizer import sanitize_label_value


def test_lowercases_input():
    assert sanitize_label_value("John.Doe") == "john.doe"


def test_strips_disallowed_characters():
    assert sanitize_label_value("john doe (admin)!") == "johndoeadmin"


def test_keeps_allowed_special_characters():
    assert sanitize_label_value("svc-account_1@corp.local") == "svc-account_1@corp.local"


def test_truncates_to_63_chars():
    long_name = "a" * 100
    result = sanitize_label_value(long_name)
    assert len(result) == 63
    assert result == "a" * 63


def test_prefixes_when_starting_with_digit():
    result = sanitize_label_value("123-account")
    assert result.startswith("user.")
    assert result[0].isalpha()


def test_prefixes_when_empty_after_cleaning():
    result = sanitize_label_value("!!!###")
    assert result.startswith("user.")


def test_prefix_respects_length_limit():
    long_numeric_name = "9" * 100
    result = sanitize_label_value(long_numeric_name)
    assert len(result) == 63
    assert result.startswith("user.")


def test_already_valid_name_is_unchanged():
    assert sanitize_label_value("alice") == "alice"
