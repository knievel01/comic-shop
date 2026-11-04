import json
import uuid
from datetime import date

from comic_helper import marktpreis
from comic_helper.config import pricing_config

from .conftest import upload_scan
from .test_flow import H, env  # noqa: F401  (fixture)

BL = "https://www.booklooker.de/B%C3%BCcher/Angebote/titel=Asterix"
ZV = "https://www.zvab.com/buch-suchen/titel/asterix/"


def offers(*pairs):
    return [marktpreis.Angebot(preis=p, url=u) for p, u in pairs]


def test_parse_keeps_only_known_portals_and_dedupes():
    text = "Treffer: " + json.dumps({"angebote": [
        {"preis": 5, "url": BL}, {"preis": 5, "url": BL}, {"preis": 7, "url": "https://example.org/x"},
        {"preis": -1, "url": ZV}, {"preis": 6.5, "url": ZV}]})
    assert [(o.preis, marktpreis.portal_of(o.url)) for o in marktpreis.parse_offers(text)] == [
        (5, "Booklooker"), (6.5, "ZVAB")]
    assert marktpreis.parse_offers("kein json") == []
    assert marktpreis.parse_offers("{kaputt}") == []


def test_median_note_and_nearest_receipt():
    cfg = pricing_config()
    s = marktpreis.build_suggestion(offers((3, BL), (5, ZV), (50, BL), (6, ZV)), cfg, today=date(2026, 11, 3))
    assert s["basis_z1"] == 5.5 and s["quelle"] == "booklooker"
    assert s["beleg"] == ZV  # nearest to the median (5 and 6 tie -> cheaper)
    assert "Median von 4 Angeboten (2 bei Booklooker, 2 bei ZVAB) = 5,50 €" in s["notiz"]
    assert "03.11.2026" in s["notiz"] and BL in s["notiz"] and "ohne Versand" in s["notiz"]


def test_too_few_offers_gives_no_suggestion():
    assert marktpreis.build_suggestion(offers((5, BL)), pricing_config()) is None


def test_recognition_stores_suggestion_and_prefills_form(env):  # noqa: F811
    env.claude.offers = [(4.0, BL), (6.0, ZV), (8.0, BL)]
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    assert c.post(f"/api/scans/{cid}/recognize", headers=H).status_code == 200
    page = c.get(f"/review/{cid}").text
    assert "Vorschlag booklooker: 6.00" in page and "Median von 3 Angeboten" in page
    assert "Automatischer Preisvorschlag" in page  # note prefilled
    assert 'value="6.00"' in page


def test_search_failure_falls_back_to_cover_price(env):  # noqa: F811
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    assert c.post(f"/api/scans/{cid}/recognize", headers=H).status_code == 200
    assert "Vorschlag aus Coverpreis" in c.get(f"/review/{cid}").text


def test_search_again_route(env):  # noqa: F811
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{cid}/recognize", headers=H)
    r = c.post(f"/review/{cid}/preis-suchen", follow_redirects=False)
    assert r.status_code == 303 and "fehler=" in r.headers["location"]
    env.claude.offers = [(10.0, BL), (12.0, ZV)]
    r = c.post(f"/review/{cid}/preis-suchen", follow_redirects=False)
    assert r.headers["location"] == f"/review/{cid}"
    assert "Vorschlag booklooker: 11.00" in c.get(f"/review/{cid}").text


def test_empty_search_is_explained(env):  # noqa: F811
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{cid}/recognize", headers=H)
    assert "keine passenden Angebote" in c.get(f"/review/{cid}").text


def test_parse_offers_takes_last_json_after_prose():
    text = (
        'Ich habe {zwei Treffer} gefunden, Entwurf: {"angebote": []}\n'
        '```json\n{"angebote": [{"preis": 7.5, "beschreibung": "Ehapa 1980", '
        '"url": "https://www.booklooker.de/x"}]}\n```'
    )
    offers = marktpreis.parse_offers(text)
    assert [o.preis for o in offers] == [7.5]
