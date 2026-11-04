"""End-to-end flow through the HTTP API with fake Claude and fake Shopify:
scan -> claim -> recognize -> review -> Shopify -> finalize -> sale webhook -> cancel."""

import base64
import hashlib
import hmac
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
from comic_helper.recognition import Erkennung, Feld
from comic_helper.shopify import Shopify

from .conftest import BUCKET, upload_scan

TOKEN = "t0ken"
SECRET = "whsec"


def feld(w, s=0.95):
    return Feld(wert=w, sicherheit=s)


class FakeClaude:
    def __init__(self, titel_sicherheit=0.95, stop_reason="end_turn"):
        self.calls = 0
        self.titel_sicherheit = titel_sicherheit
        self.stop_reason = stop_reason
        self.offers = []  # (price, url) the fake web search "finds"
        self.search_calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self.parse))
        self.messages = SimpleNamespace(create=self.search)

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        assert kwargs["tools"][0]["allowed_domains"] == ["booklooker.de", "zvab.com"]
        body = {"angebote": [{"preis": p, "beschreibung": "gut", "url": u} for p, u in self.offers]}
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="Hier: " + json.dumps(body))])

    def parse(self, **kwargs):
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
        self.calls = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        q, v = body["query"], body["variables"]
        op = re.search(r"(productVariantsBulkCreate|productVariants|productByIdentifier|productCreate|publishablePublish)", q).group(1)
        self.calls.append(op)
        if op == "productVariants":
            sku = v["q"].removeprefix("sku:")
            nodes = [dict(var, product={"id": p["id"]}) for p in self.products.values() for var in p["variants"] if var["sku"] == sku]
            data = {"productVariants": {"nodes": nodes}}
        elif op == "productByIdentifier":
            p = self.products.get(v["handle"])
            data = {"productByIdentifier": p and {"id": p["id"], "variants": {"nodes": p["variants"]}}}
        elif op == "productCreate":
            pid = f"gid://shopify/Product/{len(self.products) + 1}"
            self.products[v["product"]["handle"]] = {"id": pid, "variants": [], "input": v["product"]}
            data = {"productCreate": {"product": {"id": pid}, "userErrors": []}}
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
    settings = Settings(s3_bucket=BUCKET, helper_token=TOKEN, shopify_webhook_secret=SECRET,
                        review_base_url="https://comics-01", n8n_internal_url="http://127.0.0.1:9")
    claude = FakeClaude()
    shop_api = FakeShopifyAPI()
    shop = Shopify("test.myshopify.com", "tok", "2026-07", "1", transport=httpx2.MockTransport(shop_api))
    app = app_module.app
    app.dependency_overrides = {
        app_module.get_settings: lambda: settings,
        app_module.get_store: lambda: store,
        app_module.get_claude: lambda: claude,
        app_module.get_shopify: lambda: shop,
        app_module.get_cfg: load_pricing,
    }
    yield SimpleNamespace(client=TestClient(app), claude=claude, shop=shop_api, s3=s3, store=store)
    app.dependency_overrides = {}


H = {"X-Helper-Token": TOKEN}


def signed(payload: dict, topic: str):
    raw = json.dumps(payload).encode()
    sig = base64.b64encode(hmac.new(SECRET.encode(), raw, hashlib.sha256).digest()).decode()
    return raw, {**H, "X-Shopify-Hmac-Sha256": sig, "X-Shopify-Topic": topic, "Content-Type": "application/json"}


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
    assert f'href="/review/{cid}"' in page.text   # still opens, read-only, to take it back (ADR-0020)
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
    assert 'id="status-aktiv"' in page and "Im Shop" in page and 'class="fall panel im-shop"' in page
    assert f'/review/bild/{cid}/1' in page and f'href="/review/{cid}"' not in page
    assert "Zustand 2 · 5,99 €" in page and "Offene Comics (0)" in page

    # sale: exactly this copy moves to verkauft/; duplicate delivery changes nothing
    order = {"id": 1, "name": "#1001", "line_items": [{"sku": sku}, {"sku": "GUTSCHEIN"}]}
    raw, hdr = signed(order, "orders/paid")
    res = c.post("/api/shopify/webhook", content=raw, headers=hdr).json()["ergebnis"]
    assert res[0]["status"] == "nach-verkauft" and res[1]["status"] == "keine-comic-sku"
    assert env.store.locate(cid) == "verkauft"
    meta = storage.decode_metadata(env.s3.head_object(Bucket=BUCKET, Key=f"verkauft/{cid}.pdf")["Metadata"])
    assert meta["bestellung"] == "#1001" and meta["titel"] == "Asterix"
    res = c.post("/api/shopify/webhook", content=raw, headers=hdr).json()["ergebnis"]
    assert res[0]["status"] == "bereits-erledigt"

    # cancellation moves it back
    raw, hdr = signed(order, "orders/cancelled")
    assert c.post("/api/shopify/webhook", content=raw, headers=hdr).json()["ergebnis"][0]["status"] == "nach-aktiv"
    assert env.store.locate(cid) == "aktiv"


def test_webhook_rejects_bad_hmac(env):
    raw, hdr = signed({"line_items": []}, "orders/paid")
    hdr["X-Shopify-Hmac-Sha256"] = "AAAA"
    assert env.client.post("/api/shopify/webhook", content=raw, headers=hdr).status_code == 401


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
    # work first (offen, fehler), then what is still in the pipeline (neu)
    pos = [page.index(f'id="status-{s}"') for s in ("offen", "fehler", "neu")]
    assert pos == sorted(pos)
    assert page.index(offen) < pos[1] < page.index(fehler) < pos[2]
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
    radio = re.search(r'<input type="radio" name="zustand" value="1"[^>]*>', page).group(0)
    assert "checked" not in radio  # recommendation is shown, not preselected
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
