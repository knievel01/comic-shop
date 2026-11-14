from types import SimpleNamespace

import anthropic
import httpx2

from comic_helper import inhalt
from comic_helper.inhalt import InhaltErgebnis

CFG = {"inhalt": {"aktiv": True, "schwelle": 0.8, "max_zeichen": 600, "pruefpflicht": ["wissen"]}}
PROPOSAL = {"titel": "Asterix", "untertitel": "Die goldene Sichel", "ausgabe": "5", "verlag": "Ehapa"}
GOOD = "Asterix und Obelix suchen eine neue goldene Sichel. Dafür geht es quer durch Gallien."


def ergebnis(text=GOOD, quelle="wissen", sicherheit=0.9):
    return InhaltErgebnis(text=text, quelle=quelle, sicherheit=sicherheit)


class FakeInhaltClaude:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.kwargs = result, error, None
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self.parse))

    def parse(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(stop_reason="end_turn", parsed_output=self.result, model=kwargs["model"],
                               usage=SimpleNamespace(input_tokens=1200, output_tokens=150))


def test_bereinigen_akzeptiert_guten_text():
    assert inhalt.bereinigen(ergebnis(), CFG) == {"text": GOOD, "quelle": "wissen", "sicherheit": 0.9}


def test_bereinigen_verwirft_quelle_keine():
    assert inhalt.bereinigen(ergebnis(quelle="keine"), CFG) is None


def test_bereinigen_verwirft_ohne_text():
    assert inhalt.bereinigen(ergebnis(text=None), CFG) is None
    assert inhalt.bereinigen(ergebnis(text="   "), CFG) is None


def test_bereinigen_verwirft_unter_schwelle():
    assert inhalt.bereinigen(ergebnis(sicherheit=0.79), CFG) is None
    assert inhalt.bereinigen(ergebnis(sicherheit=0.8), CFG) is not None


def test_bereinigen_verwirft_zu_lang():
    assert inhalt.bereinigen(ergebnis(text="a" * 601), CFG) is None
    assert inhalt.bereinigen(ergebnis(text="a" * 600), CFG) is not None


def test_bereinigen_verwirft_html_und_links():
    for bad in ("Ein <b>tolles</b> Heft.", "Mehr unter https://example.com", "Siehe www.example.com", "a &amp; b"):
        assert inhalt.bereinigen(ergebnis(text=bad), CFG) is None, bad


def test_bereinigen_trimmt_leerraum():
    assert inhalt.bereinigen(ergebnis(text=f"  {GOOD}\n"), CFG)["text"] == GOOD


def test_prompt_enthaelt_regeln_und_angaben():
    p = inhalt.prompt(PROPOSAL, CFG)
    for needle in ("eigenen Worten", "spoilerfrei", "nichts erfinden", "Im Zweifel", "Asterix",
                   "Die goldene Sichel", "Ehapa", "600"):
        assert needle in p, needle


def test_schreibe_nutzt_rueckseite_und_modell():
    claude = FakeInhaltClaude(ergebnis(quelle="rueckseite"))
    usage = {}
    out = inhalt.schreibe(claude, PROPOSAL, b"jpegbytes", "claude-sonnet-5-5", "low", CFG, usage_out=usage)
    assert out == {"text": GOOD, "quelle": "rueckseite", "sicherheit": 0.9}
    assert claude.kwargs["model"] == "claude-sonnet-5-5"
    assert claude.kwargs["output_format"] is InhaltErgebnis
    assert any(b["type"] == "image" for b in claude.kwargs["messages"][0]["content"])
    assert claude.kwargs["fallbacks"] == "default"  # sonnet-5-5 supports the server-side refusal fallback
    assert usage["model"] == "claude-sonnet-5-5" and usage["input_tokens"] == 1200 and usage["output_tokens"] == 150


def test_schreibe_ohne_rueckseite_nutzt_nur_wissen():
    claude = FakeInhaltClaude(ergebnis())
    assert inhalt.schreibe(claude, PROPOSAL, None, "claude-sonnet-5-5", "low", CFG) is not None
    assert not any(b["type"] == "image" for b in claude.kwargs["messages"][0]["content"])


def test_schreibe_gibt_bei_api_fehler_none_und_wirft_nicht():
    err = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com"))
    usage = {}
    assert inhalt.schreibe(FakeInhaltClaude(error=err), PROPOSAL, b"x", "claude-sonnet-5-5", "low", CFG,
                           usage_out=usage) is None
    assert usage["fehler"]


def test_schreibe_gibt_none_bei_verworfenem_text():
    claude = FakeInhaltClaude(ergebnis(quelle="keine", text=None, sicherheit=0.0))
    assert inhalt.schreibe(claude, PROPOSAL, b"x", "claude-sonnet-5-5", "low", CFG) is None
