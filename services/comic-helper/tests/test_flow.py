"""End-to-end flow through the HTTP API with fake Claude and fake Shopify:
scan -> claim -> recognize -> review -> Shopify -> finalize."""

import io
import json
import re
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import unquote_plus

import httpx2
import pytest
from fastapi.testclient import TestClient

from comic_helper import app as app_module
from comic_helper import pdf, report, storage
from comic_helper.config import Settings, load_pricing
from comic_helper.inhalt import InhaltErgebnis
from comic_helper.recognition import Erkennung, Feld
from comic_helper.shopify import Shopify

from .conftest import BUCKET, upload_scan

TOKEN = "t0ken"


def feld(w, s=0.95):
    return Feld(wert=w, sicherheit=s)


class FakeClaude:
    def __init__(self, titel_sicherheit=0.95, stop_reason="end_turn"):
        self.calls = 0
        self.titel_sicherheit = titel_sicherheit
        self.stop_reason = stop_reason
        self.offers = []  # (price, url) the fake web search "finds"
        self.search_calls = []
        self.inhalt = InhaltErgebnis(text="Obelix verliert seine Sichel. Eine Reise quer durch Gallien beginnt.",
                                     quelle="rueckseite", sicherheit=0.9)
        self.inhalt_error = None
        self.inhalt_calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self.parse))
        self.messages = SimpleNamespace(create=self.search)

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        assert kwargs["tools"][0]["allowed_domains"] == ["booklooker.de", "zvab.com"]
        body = {"angebote": [{"preis": p, "beschreibung": "gut", "url": u} for p, u in self.offers]}
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="Hier: " + json.dumps(body))],
                               usage=SimpleNamespace(input_tokens=500, output_tokens=40,
                                                     server_tool_use=SimpleNamespace(web_search_requests=2)))

    def parse_inhalt(self, **kwargs):
        self.inhalt_calls.append(kwargs)
        if self.inhalt_error:
            raise self.inhalt_error
        return SimpleNamespace(stop_reason="end_turn", parsed_output=self.inhalt, model=kwargs["model"],
                               usage=SimpleNamespace(input_tokens=1200, output_tokens=150))

    def parse(self, **kwargs):
        if kwargs["output_format"] is InhaltErgebnis:
            return self.parse_inhalt(**kwargs)
        self.calls += 1
        assert kwargs["model"] == "claude-opus-5-5"
        assert kwargs["fallbacks"] == "default"
        images = [b for b in kwargs["messages"][0]["content"] if b["type"] == "image"]
        assert len(images) == 2
        out = Erkennung(
            titel=feld("Asterix", self.titel_sicherheit), untertitel=feld("Asterix bei den Olympischen Spielen"),
            ausgabe=feld("12"), verlag=feld("Ehapa"), jahr=feld(str(datetime.now().year)), sprache=feld("de"),
            ean_isbn=feld("978-3-7704-0012-3"), coverpreis=feld("6.99"), waehrung=feld("EUR"),
            format=feld("Album"), auffaelligkeiten="leichter Knick oben rechts",
            zustand_empfehlung=1, zustand_begruendung="Kanten minimal bestoßen, sonst sauber.",
        )
        return SimpleNamespace(stop_reason=self.stop_reason, parsed_output=out, model=kwargs["model"],
                               usage=SimpleNamespace(input_tokens=3000, output_tokens=400))


class FakeShopifyAPI:
    """Minimal in-memory Admin GraphQL for the operations shopify.py uses."""

    def __init__(self):
        self.products = {}   # handle -> {id, variants: [...]}
        self.metafields = {}  # product id -> {"value", "type"} (comic.inhalt)
        self.metafield_error = None
        self.calls = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        q, v = body["query"], body["variables"]
        op = re.search(r"(productVariantsBulkCreate|productVariants|productByIdentifier|productCreate|productUpdate|publishablePublish|metafieldsSet|products(?=\())", q).group(1)
        self.calls.append(op)
        if op == "productVariants":
            sku = v["q"].removeprefix("sku:")
            nodes = [dict(var, product={"id": p["id"]}) for p in self.products.values() for var in p["variants"] if var["sku"] == sku]
            data = {"productVariants": {"nodes": nodes}}
        elif op == "productByIdentifier":
            p = self.products.get(v["handle"])
            data = {"productByIdentifier": p and {"id": p["id"], "descriptionHtml": p["input"]["descriptionHtml"],
                                                  "metafield": self.metafields.get(p["id"]),
                                                  "variants": {"nodes": p["variants"]}}}
        elif op == "products":
            data = {"products": {"nodes": [
                {"id": p["id"], "handle": h, "title": p["input"]["title"], "metafield": self.metafields.get(p["id"])}
                for h, p in self.products.items()], "pageInfo": {"hasNextPage": False, "endCursor": None}}}
        elif op == "metafieldsSet":
            (m,) = v["metafields"]
            assert (m["namespace"], m["key"], m["type"]) == ("comic", "inhalt", "multi_line_text_field")
            if self.metafield_error:
                data = {"metafieldsSet": {"metafields": [], "userErrors": [{"field": ["metafields"], "message": self.metafield_error}]}}
            else:
                self.metafields[m["ownerId"]] = {"value": m["value"], "type": m["type"]}
                data = {"metafieldsSet": {"metafields": [{"id": "gid://shopify/Metafield/1"}], "userErrors": []}}
        elif op == "productCreate":
            pid = f"gid://shopify/Product/{len(self.products) + 1}"
            self.products[v["product"]["handle"]] = {"id": pid, "variants": [], "input": v["product"]}
            data = {"productCreate": {"product": {"id": pid}, "userErrors": []}}
        elif op == "productUpdate":
            p = next(p for p in self.products.values() if p["id"] == v["product"]["id"])
            p["input"]["descriptionHtml"] = v["product"]["descriptionHtml"]
            data = {"productUpdate": {"product": {"id": p["id"]}, "userErrors": []}}
        elif op == "productVariantsBulkCreate":
            p = next(p for p in self.products.values() if p["id"] == v["productId"])
            out = []
            for var in v["variants"]:
                vid = f"gid://shopify/ProductVariant/{sum(len(x['variants']) for x in self.products.values()) + 100}"
                rec = {"id": vid, "sku": var["inventoryItem"]["sku"], "price": var["price"],
                       "selectedOptions": [{"name": o["optionName"], "value": o["name"]} for o in var["optionValues"]],
                       "qty": var["inventoryQuantities"][0]["availableQuantity"]}
                p["variants"].append(rec)
                out.append({"id": vid, "sku": rec["sku"]})
            data = {"productVariantsBulkCreate": {"productVariants": out, "userErrors": []}}
        else:
            data = {"publishablePublish": {"userErrors": []}}
        return httpx2.Response(200, json={"data": data})


@pytest.fixture
def env(s3, store):
    settings = Settings(s3_bucket=BUCKET, helper_token=TOKEN,
                        review_base_url="https://comics-01", n8n_internal_url="http://127.0.0.1:9")
    claude = FakeClaude()
    cfg = load_pricing()
    shop_api = FakeShopifyAPI()
    shop = Shopify("test.myshopify.com", "tok", "2026-07", "1", transport=httpx2.MockTransport(shop_api))
    app = app_module.app
    app.dependency_overrides = {
        app_module.get_settings: lambda: settings,
        app_module.get_store: lambda: store,
        app_module.get_claude: lambda: claude,
        app_module.get_shopify: lambda: shop,
        app_module.get_cfg: lambda: cfg,
    }
    yield SimpleNamespace(client=TestClient(app), claude=claude, shop=shop_api, s3=s3, store=store, cfg=cfg)
    app.dependency_overrides = {}


H = {"X-Helper-Token": TOKEN}


def review_form(**over):
    form = dict(titel="Asterix", untertitel="Asterix bei den Olympischen Spielen", ausgabe="12", verlag="Ehapa",
                jahr="2025", sprache="de", ean_isbn="9783770400123", format="Album", zustand="2",
                basis_z1="10,00", preisquelle="comicguide", preis_override="", notiz="")
    form.update(over)
    return form


def test_token_required(env):
    assert env.client.post("/api/scans/claim").status_code == 401
    assert env.client.get("/healthz").status_code == 200


def test_full_lifecycle(env):
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)

    # ingest: claimed exactly once
    assert c.post("/api/scans/claim", headers=H).json()["ids"] == [cid]
    assert c.post("/api/scans/claim", headers=H).json()["ids"] == []

    # recognition
    r = c.post(f"/api/scans/{cid}/recognize", headers=H)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["titel"], body["ki_status"], body["review_url"]) == ("Asterix", "sicher", f"https://comics-01/review/{cid}")
    side = env.store.read_json(f"eingang/{cid}.json")
    assert side["preis_vorschlag"] == {"basis_z1": 4.66, "quelle": "coverpreis"}  # 6.99 EUR, current year
    assert env.store.get_tags(f"eingang/{cid}.pdf")["status"] == "offen"
    assert env.store.exists(f"bilder/{cid}-1.jpg") and env.store.exists(f"bilder/{cid}-2.jpg")
    # repeated call (e.g. n8n retry) does not call Claude again
    assert c.post(f"/api/scans/{cid}/recognize", headers=H).json()["bereits_erkannt"] is True
    assert env.claude.calls == 1

    # review UI
    page = c.get("/review/")
    assert page.status_code == 200 and "Asterix" in page.text and "Zu prüfen" in page.text
    form = c.get(f"/review/{cid}")
    assert form.status_code == 200 and "4.66" in form.text and "Zu prüfen" in form.text
    assert c.get(f"/review/bild/{cid}/1").headers["content-type"] == "image/jpeg"
    r = c.post(f"/review/{cid}", data=review_form(), follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/review/?fertig=1"
    side = env.store.read_json(f"eingang/{cid}.json")
    assert side["entscheidung"]["preis"]["final"] == 5.99   # 10 x 0.4 x 1.5 = 6.00 -> 5.99
    assert side["entscheidung"]["korrigiert"] is False
    assert c.get("/api/scans/confirmed", headers=H).json()["ids"] == [cid]
    # confirmed copy stays visible with its status until Shopify, but no longer counts as open
    page = c.get("/review/?fertig=1")
    assert "Offene Comics (0)" in page.text and 'id="status-bestaetigt"' in page.text
    assert 'id="status-offen"' not in page.text   # empty groups are not shown
    assert f'href="/review/{cid}"' in page.text   # still opens, read-only, to take it back (ADR-0006)
    # second submit is rejected
    assert c.post(f"/review/{cid}", data=review_form(), follow_redirects=False).status_code == 409

    # finalize before Shopify is refused (Shopify first, so the variant id is known)
    assert c.post(f"/api/scans/{cid}/finalize", headers=H).status_code == 409

    # Shopify, idempotent
    r = c.post(f"/api/scans/{cid}/shopify", headers=H).json()
    sku = r["sku"]
    assert sku == f"asterix-12-z2-{storage.short_id(cid)}" and r["exemplar"] == "a" and r["created"]
    assert c.post(f"/api/scans/{cid}/shopify", headers=H).json()["created"] is False
    product = env.shop.products["asterix-12-ehapa"]
    assert [(v["sku"], v["price"], v["qty"]) for v in product["variants"]] == [(sku, "5.99", 1)]

    # finalize: metadata + move to aktiv/
    r = c.post(f"/api/scans/{cid}/finalize", headers=H).json()
    assert r["status"] == "aktiv"
    head = env.s3.head_object(Bucket=BUCKET, Key=f"aktiv/{cid}.pdf")
    meta = storage.decode_metadata(head["Metadata"])
    assert meta["titel"] == "Asterix" and meta["zustand"] == "2" and meta["preis-final"] == "5.99"
    assert meta["preis-quelle"] == "comicguide" and meta["sku"] == sku and meta["shopify-variant-id"]
    assert meta["exemplar-id"] == cid and meta["ki-konfidenz"] == "0.95"
    assert c.post(f"/api/scans/{cid}/finalize", headers=H).json()["bereits_erledigt"] is True
    # copies in the shop stay visible in their own greyed-out group, read-only and not counted as open
    page = c.get("/review/").text
    assert 'id="status-aktiv"' in page and "Zuletzt in den Shop" in page and 'class="fall panel im-shop"' in page
    assert f'/review/bild/{cid}/1' in page and f'href="/review/{cid}"' not in page
    assert "Zustand 2 · 5,99 €" in page and "Offene Comics (0)" in page


def test_shop_group_shows_only_last_copies(env):
    """Sold copies stay in aktiv/ (ADR-0025), so the review shows only the latest SHOP_LIST_LIMIT."""
    for _ in range(app_module.SHOP_LIST_LIMIT + 1):
        upload_scan(env.s3, str(uuid.uuid4()), prefix="aktiv", tags="status=aktiv")
    page = env.client.get("/review/").text
    assert page.count('class="fall panel im-shop"') == app_module.SHOP_LIST_LIMIT == 30


def test_second_copy_gets_next_exemplar_letter(env):
    c = env.client
    ids = [str(uuid.uuid4()) for _ in range(2)]
    for cid in ids:
        upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    skus = []
    for cid in ids:
        c.post(f"/api/scans/{cid}/recognize", headers=H)
        c.post(f"/review/{cid}", data=review_form(), follow_redirects=False)
        skus.append(c.post(f"/api/scans/{cid}/shopify", headers=H).json())
    assert [s["exemplar"] for s in skus] == ["a", "b"]
    assert skus[0]["product_id"] == skus[1]["product_id"]
    assert env.shop.calls.count("productCreate") == 1


def test_review_validation_and_override(env):
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{cid}/recognize", headers=H)
    r = c.post(f"/review/{cid}", data=review_form(basis_z1=""), follow_redirects=False)
    assert r.status_code == 303 and "fehler=" in r.headers["location"]
    r = c.post(f"/review/{cid}", data=review_form(titel="Asterix Mega", preis_override="7,50"), follow_redirects=False)
    assert r.status_code == 303
    d = env.store.read_json(f"eingang/{cid}.json")["entscheidung"]
    assert d["preis"]["final"] == 7.5 and d["preis"]["ueberschrieben"] and d["korrigiert"] is True


def test_wrong_page_count_goes_to_error_path(env):
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid, pages=1)
    c.post("/api/scans/claim", headers=H)
    r = c.post(f"/api/scans/{cid}/recognize", headers=H)
    assert r.status_code == 422
    r = c.post(f"/api/scans/{cid}/fail", headers=H, json={"fehler": r.json()["detail"]})
    assert r.json()["status"] == "fehler"
    assert env.store.get_tags(f"eingang/{cid}.pdf")["status"] == "fehler"
    assert env.claude.calls == 0
    # failed case still opens in the review UI (no AI proposal, no images) and can be re-queued
    page = c.get(f"/review/{cid}")
    assert page.status_code == 200 and "Erneut erkennen" in page.text
    assert c.post(f"/review/{cid}/neu-erkennen", follow_redirects=False).status_code == 303
    assert c.post("/api/scans/claim", headers=H).json()["ids"] == [cid]


def test_review_delete_moves_to_papierkorb(env):
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    # still owned by n8n (status neu/in-arbeit): not deletable
    assert c.post(f"/review/{cid}/loeschen", follow_redirects=False).status_code == 409
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{cid}/recognize", headers=H)
    page = c.get(f"/review/{cid}").text
    assert 'action="/review/' + cid + '/loeschen"' in page and 'form="loeschen"' in page
    r = c.post(f"/review/{cid}/loeschen", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/review/?geloescht={cid}"
    assert not env.store.exists(f"eingang/{cid}.pdf") and not env.store.exists(f"eingang/{cid}.json")
    assert env.store.get_tags(f"papierkorb/{cid}.pdf")["status"] == "geloescht"
    assert env.store.exists(f"papierkorb/{cid}.json")
    assert cid not in c.get("/review/").text
    assert "gelöscht" in c.get(f"/review/?geloescht={cid}").text
    assert c.post(f"/review/{cid}/loeschen", follow_redirects=False).status_code == 404


def test_review_reopen_confirmed_copy(env):
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{cid}/recognize", headers=H)
    assert c.post(f"/review/{cid}/zurueckholen", follow_redirects=False).status_code == 409  # not confirmed yet
    c.post(f"/review/{cid}", data=review_form(titel="Asterix Mega", preisquelle="booklooker",
                                              preis_beleg="https://www.booklooker.de/app/detail.php?id=1"), follow_redirects=False)
    assert f'href="/review/{cid}"' in c.get("/review/").text  # confirmed card links to the detail view
    page = c.get(f"/review/{cid}").text
    assert "Zurückholen und ändern" in page and "Bestätigen und in den Shop</button>" not in page
    assert 'href="https://www.booklooker.de/app/detail.php?id=1"' in page and "Beleg:" in page  # clickable in the locked view
    r = c.post(f"/review/{cid}/zurueckholen", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/review/{cid}"
    assert env.store.get_tags(f"eingang/{cid}.pdf")["status"] == "offen"
    page = c.get(f"/review/{cid}").text
    assert 'value="Asterix Mega"' in page and "Bestätigen und in den Shop</button>" in page
    # once in Shopify, a confirmation can no longer be taken back
    c.post(f"/review/{cid}", data=review_form(), follow_redirects=False)
    side = env.store.read_json(f"eingang/{cid}.json")
    side["shopify"] = {"product_id": "gid://shopify/Product/1"}
    env.store.write_json(f"eingang/{cid}.json", side)
    assert c.post(f"/review/{cid}/zurueckholen", follow_redirects=False).status_code == 409
    assert "Schon in Shopify angelegt" in c.get(f"/review/{cid}").text


def test_review_pages_are_never_cached(env):
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{cid}/recognize", headers=H)
    for url in ("/review/", f"/review/{cid}", "/review/hochladen"):
        r = c.get(url)
        assert r.status_code == 200 and r.headers["cache-control"] == "no-store", url
    assert "pageshow" in c.get("/review/").text  # bfcache restore triggers a reload


def test_low_confidence_needs_recheck(env):
    env.claude.titel_sicherheit = 0.5
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    assert c.post(f"/api/scans/{cid}/recognize", headers=H).json()["ki_status"] == "nachkontrolle"


def test_refusal_is_error(env):
    env.claude.stop_reason = "refusal"
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    assert c.post(f"/api/scans/{cid}/recognize", headers=H).status_code == 502


def test_daily_report(env):
    c = env.client
    ids = [str(uuid.uuid4()) for _ in range(3)]
    for cid in ids:
        upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    for cid in ids:
        c.post(f"/api/scans/{cid}/recognize", headers=H)
    env.claude.titel_sicherheit = 0.3
    low = str(uuid.uuid4())
    upload_scan(env.s3, low)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{low}/recognize", headers=H)
    # one confirmed and moved to aktiv/
    c.post(f"/review/{ids[0]}", data=review_form(), follow_redirects=False)
    c.post(f"/api/scans/{ids[0]}/shopify", headers=H)
    c.post(f"/api/scans/{ids[0]}/finalize", headers=H)

    r = c.get("/api/report/daily", headers=H).json()
    assert (r["gescannt"], r["offen"], r["sicher"], r["nachkontrolle"]) == (4, 3, 3, 1)
    assert r["gesamt_offen"] == 3 and "Gescannt:            4" in r["text"]
    # nothing in a window that ended before the scans
    old = report.daily(env.store, now=datetime(2020, 1, 1, tzinfo=timezone.utc))
    assert old["gescannt"] == 0


def test_review_list_grouped_by_status(env):
    c = env.client
    offen, neu, fehler = (str(uuid.uuid4()) for _ in range(3))
    upload_scan(env.s3, offen)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{offen}/recognize", headers=H)
    upload_scan(env.s3, fehler)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{fehler}/fail", headers=H, json={"fehler": "kaputt"})
    upload_scan(env.s3, neu)

    page = c.get("/review/").text
    assert "Offene Comics (2)" in page
    # scans still in workflow 01 (neu) on top with live progress, then the work (offen, fehler)
    pos = [page.index(f'id="status-{s}"') for s in ("neu", "offen", "fehler")]
    assert pos == sorted(pos)
    assert pos[0] < page.index(neu) < pos[1] < page.index(offen) < pos[2] < page.index(fehler)
    assert f'href="/review/{neu}"' not in page and 'id="status-bestaetigt"' not in page


def test_lookup_links_use_title_and_subtitle(env):
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{cid}/recognize", headers=H)
    # shown with and without a cover price proposal
    for _ in range(2):
        page = c.get(f"/review/{cid}").text
        assert "comicguide.de/search?search=Asterix+Asterix+bei+den+Olympischen+Spielen" in page
        assert "search?search=Asterix+12" not in page
        side = env.store.read_json(f"eingang/{cid}.json")
        side["preis_vorschlag"] = None
        env.store.write_json(f"eingang/{cid}.json", side)


def test_scan_time_in_local_time():
    from datetime import datetime, timezone

    from comic_helper.app import _local_time
    assert _local_time("2026-07-01T10:05:00Z") == "01.07.2026 12:05"  # CEST
    assert _local_time(datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc), "%d.%m. %H:%M") == "01.01. 11:05"
    assert _local_time("") == ""


def test_booklooker_price_requires_evidence_link(env):
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{cid}/recognize", headers=H)
    page = c.get(f"/review/{cid}").text
    assert "<option selected>booklooker</option>" in page and 'name="preis_beleg"' in page
    # cover price proposal is shown but does not prefill a booklooker base
    assert 'id="basis" inputmode="decimal"\n            value=""' in page
    form = review_form(basis_z1="4,50", zustand="1", preisquelle="booklooker")
    r = c.post(f"/review/{cid}", data=form, follow_redirects=False)
    assert "Beleg+fehlt" in r.headers["location"]
    r = c.post(f"/review/{cid}", data={**form, "preis_beleg": "ftp://x"}, follow_redirects=False)
    assert "fehler=" in r.headers["location"]
    link = "https://www.booklooker.de/B%C3%BCcher/Asterix-25/id/A02xyz"
    r = c.post(f"/review/{cid}", data={**form, "preis_beleg": link}, follow_redirects=False)
    assert r.status_code == 303 and "fehler=" not in r.headers["location"]
    p = env.store.read_json(f"eingang/{cid}.json")["entscheidung"]["preis"]
    assert (p["quelle"], p["aufschlag"], p["final"], p["beleg"]) == ("booklooker", 1.0, 4.5, link)


def _photo(color: str, size=(3000, 4000), fmt="JPEG") -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, fmt)
    return buf.getvalue()


def test_photo_upload_creates_scan_like_the_scanner(env):
    c = env.client
    assert "Comic hochladen" in c.get("/review/hochladen").text
    files = {"cover": ("c.jpg", _photo("red"), "image/jpeg"),
             "rueckseite": ("r.webp", _photo("blue", (800, 600), "WEBP"), "image/webp")}
    r = c.post("/review/hochladen", files=files, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/review/?hochgeladen=")
    cid = r.headers["location"].split("=", 1)[1]
    key = f"eingang/{cid}.pdf"
    assert env.store.get_tags(key) == {"status": "neu"}
    assert env.store.head(key)["ContentType"] == "application/pdf"
    assert pdf.page_count(env.store.get_bytes(key)) == 2
    # from here on it is an ordinary scan
    assert cid in c.post("/api/scans/claim", headers=H).json()["ids"]
    assert c.post(f"/api/scans/{cid}/recognize", headers=H).status_code == 200
    assert "Hochgeladen als" in c.get(f"/review/?hochgeladen={cid}").text


def test_photo_upload_rejects_non_images(env):
    files = {"cover": ("c.txt", b"no image", "text/plain"), "rueckseite": ("r.jpg", _photo("blue"), "image/jpeg")}
    r = env.client.post("/review/hochladen", files=files, follow_redirects=False)
    assert "fehler=" in r.headers["location"] and "Cover" in unquote_plus(r.headers["location"])
    assert not list(env.store.list_scans("eingang"))


def test_review_list_has_upload_dialog(env):
    page = env.client.get("/review/").text
    assert page.count('id="plus"') == 1 and page.count('<dialog class="hochladen"') == 1
    assert 'action="/review/hochladen"' in page and 'name="rueckseite"' in page


def test_booklooker_proposal_prefills_price_and_evidence(env):
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{cid}/recognize", headers=H)
    side = env.store.read_json(f"eingang/{cid}.json")
    link = "https://www.booklooker.de/B%C3%BCcher/Angebote/titel=Asterix"
    side["preis_vorschlag"] = {"basis_z1": 7.95, "quelle": "booklooker", "beleg": link, "hinweis": "Median aus 4 Angeboten"}
    env.store.write_json(f"eingang/{cid}.json", side)
    page = c.get(f"/review/{cid}").text
    assert 'value="7.95"' in page and f'value="{link}"' in page and "Median aus 4 Angeboten" in page


def test_condition_recommendation_shown_not_preselected(env):
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{cid}/recognize", headers=H)
    side = env.store.read_json(f"eingang/{cid}.json")
    assert (side["vorschlag"]["zustand_ki"], side["vorschlag"]["zustand_ki_begruendung"]) == (1, "Kanten minimal bestoßen, sonst sauber.")
    page = c.get(f"/review/{cid}").text
    assert "KI-Zustandsempfehlung:" in page and "1 – sehr gut" in page and "KI-Empfehlung</span>" in page
    stufe = re.search(r'<input type="checkbox" name="zustand" value="1"[^>]*>', page).group(0)
    assert "checked" not in stufe  # recommendation is shown, not preselected
    assert 'id="entwurf"' in page and "comics-entwurf:" in page  # draft autosave in browser storage


def test_condition_prompt_uses_scale_from_config():
    from comic_helper.config import load_pricing
    from comic_helper.recognition import system_prompt
    p = system_prompt(load_pricing()["zustaende"])
    assert "zustand_empfehlung" in p and "- 1 sehr gut: Gelesen, aber sehr gepflegt." in p


def test_review_fonts_are_served_locally(env):
    r = env.client.get("/review/static/fonts/Bangers-Regular.ttf")
    assert r.status_code == 200 and len(r.content) > 10_000


def test_upload_triggers_workflow_01(env, monkeypatch):
    calls = []
    monkeypatch.setattr(app_module.httpx2, "post", lambda url, **kw: calls.append((url, kw)))
    files = {"cover": ("c.jpg", _photo("red"), "image/jpeg"), "rueckseite": ("r.jpg", _photo("red"), "image/jpeg")}
    assert env.client.post("/review/hochladen", files=files, follow_redirects=False).status_code == 303
    assert len(calls) == 1 and calls[0][0].endswith("/webhook/scan-neu")
    assert calls[0][1]["headers"]["X-Helper-Token"] == TOKEN


def _upload_lot(env, monkeypatch, anzahl: str) -> str:
    monkeypatch.setattr(app_module.httpx2, "post", lambda url, **kw: None)
    files = {"cover": ("c.jpg", _photo("red"), "image/jpeg"), "rueckseite": ("r.jpg", _photo("red"), "image/jpeg")}
    r = env.client.post("/review/hochladen", files=files, data={"anzahl": anzahl}, follow_redirects=False)
    assert r.status_code == 303, r.headers["location"]
    return r.headers["location"].split("hochgeladen=")[1]


def test_lot_from_upload_to_shopify(env, monkeypatch):
    """ADR-0012: one sample photo, 20 copies, condition range 1-3 -> one variant with quantity 20."""
    c = env.client
    cid = _upload_lot(env, monkeypatch, "20")
    assert env.store.get_tags(f"eingang/{cid}.pdf") == {"status": "neu", "anzahl": "20"}
    c.post("/api/scans/claim", headers=H)
    assert c.post(f"/api/scans/{cid}/recognize", headers=H).status_code == 200
    assert env.store.get_tags(f"eingang/{cid}.pdf")["anzahl"] == "20"   # survives the status change
    assert 'name="anzahl" id="anzahl" min="1" max="999" value="20"' in c.get(f"/review/{cid}").text

    # 1 and 3 chosen: the range is filled in, price factor = mean of 1.0, 0.4, 0.2
    r = c.post(f"/review/{cid}", data=review_form(zustand=["1", "3"], anzahl="20"), follow_redirects=False)
    assert r.status_code == 303 and "fehler" not in r.headers["location"]
    d = env.store.read_json(f"eingang/{cid}.json")["entscheidung"]
    assert (d["zustand"], d["zustaende"], d["anzahl"]) == ("1-3", [1, 2, 3], 20)
    assert d["preis"]["faktor"] == 0.5333 and d["preis"]["final"] == 7.99   # 10 x 0.5333 x 1.5 = 8.00

    sku = c.post(f"/api/scans/{cid}/shopify", headers=H).json()["sku"]
    assert sku == f"asterix-12-z1-3-{storage.short_id(cid)}"
    product = env.shop.products["asterix-12-ehapa"]
    variant = product["variants"][0]
    assert variant["qty"] == 20 and variant["price"] == "7.99"
    assert {"name": "Zustand", "value": "Sammelposten · Zustand 1–3"} in variant["selectedOptions"]
    desc = product["input"]["descriptionHtml"]
    assert "Sammelposten:</strong> Von diesem Heft haben wir mehrere Exemplare." in desc
    assert "Zustand 1 bis 3 (sehr gut bis noch sammelwürdig), nie schlechter" in desc

    meta = c.post(f"/api/scans/{cid}/finalize", headers=H).json()["metadata"]
    assert (meta["zustand"], meta["anzahl"]) == ("1-3", 20)
    assert "20× · Zustand 1–3 · 7,99 €" in c.get("/review/").text


def test_lot_added_to_existing_product_explains_lots_once(env, monkeypatch):
    c = env.client
    for zustand, anzahl in (("2", "1"), (["2", "3"], "5"), (["1", "2"], "8")):
        cid = str(uuid.uuid4())
        upload_scan(env.s3, cid)
        c.post("/api/scans/claim", headers=H)
        c.post(f"/api/scans/{cid}/recognize", headers=H)
        c.post(f"/review/{cid}", data=review_form(zustand=zustand, anzahl=anzahl))
        assert c.post(f"/api/scans/{cid}/shopify", headers=H).status_code == 200
    product = env.shop.products["asterix-12-ehapa"]
    assert [v["qty"] for v in product["variants"]] == [1, 5, 8]
    assert product["input"]["descriptionHtml"].count("Sammelposten:</strong>") == 1
    assert "Zustand 2 bis 3 (gut bis noch sammelwürdig)" in product["input"]["descriptionHtml"]
    assert env.shop.calls.count("productUpdate") == 1


def test_several_conditions_need_a_lot(env):
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{cid}/recognize", headers=H)
    r = c.post(f"/review/{cid}", data=review_form(zustand=["1", "2"], anzahl="1"), follow_redirects=False)
    assert "Mehrere+Zust%C3%A4nde" in r.headers["location"]
    r = c.post(f"/review/{cid}", data=review_form(zustand=[], anzahl="1"), follow_redirects=False)
    assert "Zustand+fehlt" in r.headers["location"]
    assert env.store.get_tags(f"eingang/{cid}.pdf")["status"] == "offen"


def test_upload_rejects_invalid_count(env, monkeypatch):
    monkeypatch.setattr(app_module.httpx2, "post", lambda url, **kw: None)
    files = {"cover": ("c.jpg", _photo("red"), "image/jpeg"), "rueckseite": ("r.jpg", _photo("red"), "image/jpeg")}
    r = env.client.post("/review/hochladen", files=files, data={"anzahl": "0"}, follow_redirects=False)
    assert "Anzahl" in unquote_plus(r.headers["location"])


# --- Inhaltstext (ADR-0010) ------------------------------------------------------------------------
def recognized(env, inhalt_aktiv=True):
    env.cfg["inhalt"]["aktiv"] = inhalt_aktiv
    cid = str(uuid.uuid4())
    upload_scan(env.s3, cid)
    env.client.post("/api/scans/claim", headers=H)
    r = env.client.post(f"/api/scans/{cid}/recognize", headers=H)
    assert r.status_code == 200, r.text
    return cid


def test_recognize_schreibt_inhalt_in_den_vorschlag(env):
    cid = recognized(env)
    side = env.store.read_json(f"eingang/{cid}.json")
    assert side["vorschlag"]["inhalt"]["quelle"] == "rueckseite"
    assert side["vorschlag"]["inhalt"]["text"].startswith("Obelix")
    run = side["laeufe"][-1]["inhalt"]
    assert run["input_tokens"] == 1200 and run["output_tokens"] == 150 and run["modell"] == "claude-opus-5-5"
    assert len(env.claude.inhalt_calls) == 1
    assert env.store.get_tags(f"eingang/{cid}.pdf").get("schritt") in (None, "")  # cleared when done


def test_recognize_bleibt_offen_wenn_inhalt_fehlschlaegt(env):
    env.claude.inhalt_error = RuntimeError("boom")
    cid = recognized(env)
    side = env.store.read_json(f"eingang/{cid}.json")
    assert side["vorschlag"]["inhalt"] is None
    assert side["laeufe"][-1]["inhalt"]["fehler"]
    assert env.store.get_tags(f"eingang/{cid}.pdf")["status"] == "offen"


def test_recognize_ohne_schalter_ruft_inhalt_nicht_auf(env):
    cid = recognized(env, inhalt_aktiv=False)
    side = env.store.read_json(f"eingang/{cid}.json")
    assert "inhalt" not in side["vorschlag"] and side["laeufe"][-1]["inhalt"] is None
    assert env.claude.inhalt_calls == []


def test_inhalt_endpunkt_schreibt_neu(env):
    cid = recognized(env)
    assert env.client.post(f"/api/scans/{cid}/inhalt").status_code == 401
    r = env.client.post(f"/api/scans/{cid}/inhalt", headers=H)
    assert r.status_code == 200 and r.json()["text"].startswith("Obelix")
    assert len(env.claude.inhalt_calls) == 1  # idempotent: the draft exists already
    env.claude.inhalt = InhaltErgebnis(text="Ein ganz neuer Text.", quelle="wissen", sicherheit=0.95)
    r = env.client.post(f"/api/scans/{cid}/inhalt?neu=1", headers=H)
    assert r.json() == {"text": "Ein ganz neuer Text.", "quelle": "wissen", "sicherheit": 0.95}
    side = env.store.read_json(f"eingang/{cid}.json")
    assert side["vorschlag"]["inhalt"]["text"] == "Ein ganz neuer Text."
    assert [e["art"] for e in side["laeufe"]][-1] == "inhalt"
    env.cfg["inhalt"]["aktiv"] = False
    assert env.client.post(f"/api/scans/{cid}/inhalt?neu=1", headers=H).status_code == 409


def test_review_formular_zeigt_inhalt_und_pruefhinweis(env):
    env.claude.inhalt = InhaltErgebnis(text="Ein Text aus dem Wissen.", quelle="wissen", sicherheit=0.9)
    cid = recognized(env)
    page = env.client.get(f"/review/{cid}").text
    assert "Ein Text aus dem Wissen." in page and 'name="inhalt_geprueft"' in page and "Inhalt neu schreiben" in page
    env.cfg["inhalt"]["aktiv"] = False
    assert 'name="inhalt"' not in env.client.get(f"/review/{cid}").text


def test_review_speichert_inhalt_in_entscheidung(env):
    cid = recognized(env)
    text = "Obelix verliert seine Sichel. Eine Reise quer durch Gallien beginnt."
    r = env.client.post(f"/review/{cid}", data=review_form(inhalt=text), follow_redirects=False)
    assert r.status_code == 303 and "fehler" not in r.headers["location"]
    d = env.store.read_json(f"eingang/{cid}.json")["entscheidung"]
    assert d["inhalt"] == {"text": text, "quelle": "rueckseite", "geprueft": False}


def test_review_wissen_ohne_haken_wird_abgelehnt(env):
    env.claude.inhalt = InhaltErgebnis(text="Ein Text aus dem Wissen.", quelle="wissen", sicherheit=0.9)
    cid = recognized(env)
    form = review_form(inhalt="Ein Text aus dem Wissen.")
    r = env.client.post(f"/review/{cid}", data=form, follow_redirects=False)
    assert r.status_code == 303 and "Text+gepr%C3%BCft+best%C3%A4tigen" in r.headers["location"]
    assert "entscheidung" not in env.store.read_json(f"eingang/{cid}.json")
    r = env.client.post(f"/review/{cid}", data=dict(form, inhalt_geprueft="1"), follow_redirects=False)
    assert "fehler" not in r.headers["location"]
    inhalt = env.store.read_json(f"eingang/{cid}.json")["entscheidung"]["inhalt"]
    assert inhalt["quelle"] == "wissen" and inhalt["geprueft"] is True


def test_review_leerer_inhalt_ist_erlaubt(env):
    env.claude.inhalt = InhaltErgebnis(text="Ein Text aus dem Wissen.", quelle="wissen", sicherheit=0.9)
    cid = recognized(env)
    r = env.client.post(f"/review/{cid}", data=review_form(inhalt="  "), follow_redirects=False)
    assert "fehler" not in r.headers["location"]
    assert env.store.read_json(f"eingang/{cid}.json")["entscheidung"]["inhalt"] is None


def test_review_eigener_text_ohne_vorschlag_braucht_keinen_haken(env):
    env.claude.inhalt = InhaltErgebnis(text=None, quelle="keine", sicherheit=0.0)
    cid = recognized(env)
    r = env.client.post(f"/review/{cid}", data=review_form(inhalt="Von Hand geschrieben."), follow_redirects=False)
    assert "fehler" not in r.headers["location"]
    assert env.store.read_json(f"eingang/{cid}.json")["entscheidung"]["inhalt"]["quelle"] == "manuell"


def test_review_inhalt_zu_lang_oder_mit_html_wird_abgelehnt(env):
    cid = recognized(env)
    for bad in ("x" * 601, "Ein <b>Text</b>", "Mehr auf https://example.com"):
        r = env.client.post(f"/review/{cid}", data=review_form(inhalt=bad), follow_redirects=False)
        assert "fehler=Inhalt" in r.headers["location"], bad
    assert "entscheidung" not in env.store.read_json(f"eingang/{cid}.json")


# --- Inhaltstext im Metafeld comic.inhalt (ADR-0012) --------------------------------------------------
def to_shop(env, inhalt=None, **form):
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    c.post(f"/api/scans/{cid}/recognize", headers=H)
    data = review_form(**form)
    if inhalt is not None:
        data["inhalt"] = inhalt
    assert "fehler" not in c.post(f"/review/{cid}", data=data, follow_redirects=False).headers["location"]
    r = c.post(f"/api/scans/{cid}/shopify", headers=H)
    assert r.status_code == 200, r.text
    return cid, r.json()


def test_neues_produkt_bekommt_inhalts_metafeld(env):
    env.cfg["inhalt"]["aktiv"] = True
    _, res = to_shop(env, inhalt="Obelix verliert seine Sichel.")
    product = env.shop.products["asterix-12-ehapa"]
    assert env.shop.metafields[product["id"]]["value"] == "Obelix verliert seine Sichel."
    assert res["inhalt"] == "gesetzt"


def test_weiteres_exemplar_ueberschreibt_vorhandenen_inhalt_nicht(env):
    to_shop(env, inhalt="Erster Text.")
    _, res = to_shop(env, inhalt="Zweiter Text.", zustand="3")
    product = env.shop.products["asterix-12-ehapa"]
    assert env.shop.metafields[product["id"]]["value"] == "Erster Text."
    assert env.shop.calls.count("metafieldsSet") == 1 and res["inhalt"] == "vorhanden"


def test_vorhandenes_produkt_ohne_inhalt_bekommt_ihn(env):
    to_shop(env)
    _, res = to_shop(env, inhalt="Jetzt mit Text.", zustand="3")
    product = env.shop.products["asterix-12-ehapa"]
    assert env.shop.metafields[product["id"]]["value"] == "Jetzt mit Text." and res["inhalt"] == "gesetzt"


def test_ohne_text_kein_metafieldsSet(env):
    _, res = to_shop(env)
    assert "metafieldsSet" not in env.shop.calls and res["inhalt"] == ""


def test_inhalt_wird_nicht_in_die_beschreibung_geschrieben(env):
    to_shop(env, inhalt="Geheimer Inhaltstext.")
    assert "Geheimer Inhaltstext." not in env.shop.products["asterix-12-ehapa"]["input"]["descriptionHtml"]


def test_fehler_beim_metafeld_bricht_das_anlegen_nicht_ab(env):
    env.shop.metafield_error = "Zugriff verweigert"
    cid, res = to_shop(env, inhalt="Ein Text.")
    assert res["created"] and res["inhalt"].startswith("fehler: ") and "Zugriff verweigert" in res["inhalt"]
    assert len(env.shop.products["asterix-12-ehapa"]["variants"]) == 1
    assert env.store.read_json(f"eingang/{cid}.json")["shopify"]["inhalt"].startswith("fehler: ")
