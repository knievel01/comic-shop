import pytest

from comic_helper.recognition import normalize_issue


@pytest.mark.parametrize("raw, expected", [
    ("Grosser Sonderband II", "2"),
    ("I", "1"),
    ("XIV", "14"),
    ("Band 4", "4"),
    ("Nr. 012", "12"),
    ("Sonderheft 3", "3"),
    ("1987/23", "1987/23"),
    ("12", "12"),
    ("-", "-"),
    ("", ""),
    ("3 von 5", "3 von 5"),     # ambiguous, left for the reviewer
    ("Special", "Special"),
])
def test_normalize_issue(raw, expected):
    assert normalize_issue(raw) == expected
