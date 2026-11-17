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


def test_prompt_enthaelt_inhaltsabschnitt_nur_wenn_eingeschaltet():
    from comic_helper.recognition import system_prompt
    cfg = {"inhalt": {"aktiv": True, "max_zeichen": 600}}
    p = system_prompt(None, cfg)
    assert "inhalt_text" in p and "inhalt_quelle" in p and "eigenen Worten" in p and "600" in p
    assert "Alle anderen Felder liest du weiterhin nur von den Scans ab" in p
    assert "inhalt_text" not in system_prompt(None, {"inhalt": {"aktiv": False, "max_zeichen": 600}})
    assert "inhalt_text" not in system_prompt(None)
