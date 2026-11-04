import uuid

from comic_helper import statistik
from comic_helper.config import pricing_config

from .conftest import upload_scan
from .test_flow import H, env  # noqa: F401  (fixture)
from .test_marktpreis import BL, ZV


def test_part_cost_uses_price_list():
    conf = pricing_config()["statistik"]
    part = {"modell": "claude-sonnet-5-5", "input_tokens": 1_000_000, "output_tokens": 100_000, "suchen": 3}
    assert round(statistik.part_cost(part, conf), 4) == round(2.0 + 1.0 + 0.03, 4)
    assert statistik.part_cost(None, conf) == 0.0
    assert statistik.part_cost({"modell": "unbekannt", "input_tokens": 5}, conf) == 0.0


def test_recognition_records_run_and_page_shows_it(env):  # noqa: F811
    env.claude.offers = [(4.0, BL), (6.0, ZV), (8.0, BL)]
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    assert c.post(f"/api/scans/{cid}/recognize", headers={**H, "X-N8N-Lauf": "4711"}).status_code == 200

    side = env.store.read_json(env.store.sidecar_key("eingang", cid))
    (run,) = side["laeufe"]
    assert run["n8n"] == "4711" and run["art"] == "erkennung"
    assert run["erkennung"]["input_tokens"] > 0 and run["preissuche"]["treffer"] == 3

    page = c.get("/review/statistik/kosten")
    assert page.status_code == 200
    assert "Workflow 01 · #4711" in page.text and "(Sonnet 0,21 $)" in page.text
    saved = c.get("/review/statistik/einsparung").text
    assert "Je Workflow" in saved and "4 Min" in saved and "eingespart" in saved and "14,60 €/Std" in saved
    assert 'href="/review/statistik"' in c.get("/review/").text
    assert c.get("/review/statistik", follow_redirects=False).headers["location"] == "/review/statistik/kosten"
    assert c.get("/review/statistik/sonstwas").status_code == 404


def test_manual_price_search_adds_entry_without_n8n_id(env):  # noqa: F811
    env.claude.offers = [(4.0, BL), (6.0, ZV)]
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{cid}/recognize", headers=H)
    assert c.post(f"/review/{cid}/preis-suchen", follow_redirects=False).status_code == 303
    side = env.store.read_json(env.store.sidecar_key("eingang", cid))
    assert [e["art"] for e in side["laeufe"]] == ["erkennung", "preissuche"]
    assert "Review (manuell)" in c.get("/review/statistik/kosten").text


def test_legacy_sidecar_without_runs_still_counts_cost():
    side = {"erkannt_am": "2026-11-01T10:00:00Z", "ki_info": {"model": "claude-opus-5-5", "input_tokens": 1000,
                                                              "output_tokens": 100}}
    (e,) = statistik.entries_of(side)
    assert e["erkennung"]["sekunden"] is None and e["n8n"] == ""
