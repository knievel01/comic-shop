from types import SimpleNamespace

from comic_helper import marktpreis
from comic_helper.config import pricing_config

from .conftest import upload_scan  # noqa: F401
from .test_flow import FakeClaude

PROPOSAL = {"titel": "Asterix", "untertitel": "", "ausgabe": "1", "verlag": "Ehapa", "jahr": 2020,
            "sprache": "de", "ean_isbn": "123"}


def test_model_override_and_usage():
    cfg = pricing_config()
    cfg["marktpreis"]["modell"] = "claude-sonnet-5-5"
    claude = FakeClaude()
    models = []
    orig = claude.search

    def search(**kw):
        models.append(kw["model"])
        r = orig(**kw)
        r.usage = SimpleNamespace(input_tokens=1000, output_tokens=50,
                                  server_tool_use=SimpleNamespace(web_search_requests=3))
        return r

    claude.messages = SimpleNamespace(create=search)
    usage = {}
    marktpreis.suggest(claude, PROPOSAL, cfg, "claude-opus-5-5", usage_out=usage)
    assert set(models) == {"claude-sonnet-5-5"}
    assert usage["model"] == "claude-sonnet-5-5" and usage["searches"] == 3 * usage["attempts"]
    assert usage["input_tokens"] == 1000 * usage["attempts"]
