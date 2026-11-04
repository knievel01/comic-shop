"""comic-helper: HTTP service called by n8n (internal API) plus the LAN review UI.

Internal API (header X-Helper-Token), orchestrated by n8n:
    POST /api/scans/claim                 new scans -> in-arbeit
    POST /api/scans/{id}/recognize        render, Claude, proposal -> offen
    POST /api/scans/{id}/fail             -> fehler (error path)
    GET  /api/scans/confirmed             confirmed but not yet in Shopify (retry)
    POST /api/scans/{id}/shopify          create product/variant (idempotent)
    POST /api/scans/{id}/finalize         write S3 metadata, move to aktiv/
    POST /api/shopify/webhook             orders/paid, orders/cancelled, refunds/create
    GET  /api/report/daily                numbers for the 7 o'clock mail
    GET  /api/mail-config                 mail recipients for n8n

Review UI (LAN only, optional password): /review/, photo upload: /review/hochladen
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

import anthropic
import boto3
import httpx2
from botocore.config import Config
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import marktpreis, pdf, pricing, recognition, report, storage, webhooks
from .config import Settings, pricing_config, settings
from .shopify import Shopify, ShopifyError, make_sku
from .storage import AKTIV, EINGANG, Store

log = logging.getLogger("comic_helper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="comic-helper", docs_url=None, redoc_url=None)


@app.middleware("http")
async def no_cache_review_pages(request: Request, call_next):
    """Review pages are computed live (groups, status): never serve them from the browser cache or bfcache."""
    response = await call_next(request)
    if request.url.path.startswith("/review") and response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-store"
    return response
_render_slot = threading.Lock()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
# Fonts for the review UI, served locally so the pages make no external requests
app.mount("/review/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


def _local_time(value: datetime | str | None, fmt: str = "%d.%m.%Y %H:%M") -> str:
    """Render a UTC timestamp (datetime or ISO string) in the shop's local time."""
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(report.TZ).strftime(fmt)


templates.env.filters["lokalzeit"] = _local_time


# --- dependencies (overridden in tests) ---------------------------------------
@lru_cache
def _s3():
    s = settings()
    return boto3.client("s3", region_name=s.aws_region, endpoint_url=s.s3_endpoint_url,
                        config=Config(retries={"max_attempts": 5, "mode": "standard"}))


def get_settings() -> Settings:
    return settings()


def get_cfg() -> dict:
    return pricing_config()


def get_store() -> Store:
    return Store(_s3(), settings().s3_bucket)


def get_claude() -> anthropic.Anthropic:
    return anthropic.Anthropic(max_retries=3, timeout=300)


def get_shopify() -> Shopify:
    s = settings()
    return Shopify(s.shopify_shop_domain, s.shopify_admin_token, s.shopify_api_version,
                   s.shopify_location_id, s.shopify_publication_ids,
                   client_id=s.shopify_client_id, client_secret=s.shopify_client_secret)


def require_token(x_helper_token: str = Header(default=""), s: Settings = Depends(get_settings)) -> None:
    if not s.helper_token or not secrets.compare_digest(x_helper_token, s.helper_token):
        raise HTTPException(401, "invalid helper token")


_basic = HTTPBasic(auto_error=False)


def require_reviewer(creds: HTTPBasicCredentials | None = Depends(_basic), s: Settings = Depends(get_settings)) -> None:
    if not s.review_password:
        return
    if creds is None or not secrets.compare_digest(creds.password, s.review_password):
        raise HTTPException(401, "Anmeldung erforderlich", headers={"WWW-Authenticate": 'Basic realm="Comics"'})


def _utc(dt: datetime | None = None) -> str:
    return (dt or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _check_id(copy_id: str) -> str:
    if not storage.is_copy_id(copy_id):
        raise HTTPException(400, "invalid copy id")
    return copy_id


# --- health ---------------------------------------------------------------------
@app.get("/healthz")
@app.get("/review/healthz")
def healthz():
    return {"ok": True}


# --- ingest + recognition -----------------------------------------------------
@app.post("/api/scans/claim", dependencies=[Depends(require_token)])
def claim(limit: int = 10, store: Store = Depends(get_store)):
    return {"ids": store.claim_new(limit)}


@app.post("/api/scans/{copy_id}/recognize", dependencies=[Depends(require_token)])
def recognize(copy_id: str, store: Store = Depends(get_store), s: Settings = Depends(get_settings),
              cfg: dict = Depends(get_cfg), claude: anthropic.Anthropic = Depends(get_claude)):
    _check_id(copy_id)
    key = store.pdf_key(EINGANG, copy_id)
    try:
        head = store.head(key)
    except storage.NotFound:
        raise HTTPException(404, "scan not in eingang/")
    tags = store.get_tags(key)
    side_key = store.sidecar_key(EINGANG, copy_id)
    if tags.get("status") in ("offen", "bestaetigt") and store.exists(side_key):
        return _summary(copy_id, store.read_json(side_key), s, already=True)

    data = store.get_bytes(key)
    # n8n sends a whole batch at once; rendered pages are large, so render one scan at a time
    # and keep only the small JPEGs while waiting for Claude.
    with _render_slot:
        try:
            pages = pdf.page_count(data)
            if pages != 2:
                raise pdf.PdfError(f"{pages} Seiten statt 2")
            cover, back = (pdf.trim_margins(im) for im in pdf.render_pages(data)[:2])
        except pdf.PdfError as e:
            raise HTTPException(422, f"PDF: {e}")
        for page, im in ((1, cover), (2, back)):
            store.put_bytes(store.image_key(copy_id, page), pdf.to_jpeg(im, pdf.SHOP_MAX_EDGE), "image/jpeg")
        model_images = [pdf.to_jpeg(im, pdf.MODEL_MAX_EDGE) for im in (cover, back)]
        del cover, back

    try:
        result, info = recognition.recognize(
            claude, *model_images, model=s.anthropic_model, effort=s.anthropic_effort, zustaende=cfg["zustaende"])
    except recognition.RecognitionError as e:
        raise HTTPException(503 if e.retryable else 502, f"Erkennung: {e}")

    proposal = recognition.to_proposal(result)
    confidence = recognition.overall_confidence(result)
    ki_status = recognition.classify(confidence, float(cfg["konfidenz_schwelle"]))
    price_hint = marktpreis.suggest(claude, proposal, cfg, s.anthropic_model)
    if price_hint is None and proposal["coverpreis"] and pricing.cover_rule_applies(
            proposal["waehrung"], proposal["jahr"], cfg):
        price_hint = {"basis_z1": pricing.base_from_cover_price(proposal["coverpreis"], cfg), "quelle": "coverpreis"}

    sidecar = {
        "id": copy_id,
        "gescannt_am": _utc(head["LastModified"]),
        "erkannt_am": _utc(),
        "vorschlag": proposal,
        "konfidenz": confidence,
        "ki_status": ki_status,
        "preis_vorschlag": price_hint,
        "preis_suche": _utc(),
        "ki_roh": result.model_dump(),
        "ki_info": info,
    }
    store.write_json(side_key, sidecar)
    store.update_tags(key, status="offen", ki=ki_status, claimed=None)
    log.info("recognized %s: %s %s (%s %.2f)", copy_id, proposal["titel"], proposal["ausgabe"], ki_status, confidence)
    return _summary(copy_id, sidecar, s)


def _summary(copy_id: str, sidecar: dict, s: Settings, already: bool = False) -> dict:
    v = sidecar["vorschlag"]
    return {
        "id": copy_id,
        "status": "offen",
        "bereits_erkannt": already,
        "ki_status": sidecar["ki_status"],
        "konfidenz": sidecar["konfidenz"],
        "titel": v["titel"],
        "ausgabe": v["ausgabe"],
        "verlag": v["verlag"],
        "review_url": f"{s.review_base_url}/review/{copy_id}",
    }


@app.post("/api/scans/{copy_id}/fail", dependencies=[Depends(require_token)])
async def fail(copy_id: str, request: Request, store: Store = Depends(get_store)):
    _check_id(copy_id)
    body = await request.json() if await request.body() else {}
    key = store.pdf_key(EINGANG, copy_id)
    if not store.exists(key):
        raise HTTPException(404, "scan not in eingang/")
    side_key = store.sidecar_key(EINGANG, copy_id)
    side = store.read_json(side_key) if store.exists(side_key) else {"id": copy_id}
    side.setdefault("fehler", []).append({"am": _utc(), "fehler": str(body.get("fehler", ""))[:2000]})
    store.write_json(side_key, side)
    store.update_tags(key, status="fehler", claimed=None)
    return {"id": copy_id, "status": "fehler"}


@app.post("/api/scans/{copy_id}/retry", dependencies=[Depends(require_token)])
def retry(copy_id: str, store: Store = Depends(get_store)):
    _check_id(copy_id)
    store.update_tags(store.pdf_key(EINGANG, copy_id), status="neu", claimed=None)
    return {"id": copy_id, "status": "neu"}


# --- after confirmation: Shopify, then metadata --------------------------------
@app.get("/api/scans/confirmed", dependencies=[Depends(require_token)])
def confirmed(store: Store = Depends(get_store)):
    ids = [o.copy_id for o in store.list_scans(EINGANG) if store.get_tags(o.key).get("status") == "bestaetigt"]
    return {"ids": ids}


def _confirmed_sidecar(store: Store, copy_id: str) -> dict:
    key = store.pdf_key(EINGANG, copy_id)
    if not store.exists(key):
        if store.exists(store.pdf_key(AKTIV, copy_id)):
            raise HTTPException(409, "already finalized (aktiv/)")
        raise HTTPException(404, "scan not found")
    if store.get_tags(key).get("status") != "bestaetigt":
        raise HTTPException(409, "scan is not confirmed")
    return store.read_json(store.sidecar_key(EINGANG, copy_id))


@app.post("/api/scans/{copy_id}/shopify", dependencies=[Depends(require_token)])
def to_shopify(copy_id: str, store: Store = Depends(get_store), cfg: dict = Depends(get_cfg),
               shop: Shopify = Depends(get_shopify)):
    _check_id(copy_id)
    side = _confirmed_sidecar(store, copy_id)
    if side.get("shopify"):
        return {"id": copy_id, **side["shopify"], "created": False}
    d = side["entscheidung"]
    urls = [store.presigned_url(store.image_key(copy_id, p), 6 * 3600) for p in (1, 2)]
    try:
        res = shop.add_copy(copy_short_id=storage.short_id(copy_id), proposal=d, zustand=d["zustand"],
                            price=d["preis"]["final"], image_urls=urls, cfg=cfg)
    except (ShopifyError, httpx2.HTTPError) as e:
        raise HTTPException(502, f"Shopify: {e}")
    side["shopify"] = {"product_id": res.product_id, "variant_id": res.variant_id, "sku": res.sku,
                       "exemplar": res.exemplar, "am": _utc()}
    store.write_json(store.sidecar_key(EINGANG, copy_id), side)
    return {"id": copy_id, **side["shopify"], "created": res.created}


def final_metadata(copy_id: str, side: dict) -> dict:
    d, p, sh = side["entscheidung"], side["entscheidung"]["preis"], side["shopify"]
    return {
        "exemplar-id": copy_id,
        "titel": d["titel"][:200],
        "untertitel": (d.get("untertitel") or "")[:200],
        "ausgabe": d.get("ausgabe", ""),
        "verlag": d.get("verlag", ""),
        "jahr": d.get("jahr") or "",
        "sprache": d.get("sprache", ""),
        "ean": d.get("ean_isbn", ""),
        "ki-konfidenz": side.get("konfidenz", ""),
        "ki-status": side.get("ki_status", ""),
        "ki-zustand": (side.get("vorschlag") or {}).get("zustand_ki", ""),
        "zustand": d["zustand"],
        "preis-basis-z1": f"{p['basis_z1']:.2f}",
        "preis-quelle": p["quelle"],
        "preis-faktor": p["faktor"],
        "preis-aufschlag": p["aufschlag"],
        "preis-final": f"{p['final']:.2f}",
        "preis-ueberschrieben": "ja" if p.get("ueberschrieben") else "",
        "preis-beleg": p.get("beleg", ""),
        "sku": sh["sku"],
        "shopify-product-id": sh["product_id"].rsplit("/", 1)[-1],
        "shopify-variant-id": sh["variant_id"].rsplit("/", 1)[-1],
        "gescannt-am": side.get("gescannt_am", ""),
        "bestaetigt-am": d.get("am", ""),
    }


@app.post("/api/scans/{copy_id}/finalize", dependencies=[Depends(require_token)])
def finalize(copy_id: str, store: Store = Depends(get_store)):
    _check_id(copy_id)
    if store.exists(store.pdf_key(AKTIV, copy_id)) and not store.exists(store.pdf_key(EINGANG, copy_id)):
        return {"id": copy_id, "status": "aktiv", "bereits_erledigt": True}
    side = _confirmed_sidecar(store, copy_id)
    if not side.get("shopify"):
        raise HTTPException(409, "not yet in Shopify")
    meta = final_metadata(copy_id, side)
    store.move(copy_id, EINGANG, AKTIV, metadata=meta, tags={"status": "aktiv"})
    return {"id": copy_id, "status": "aktiv", "metadata": meta}


# --- Shopify webhooks (forwarded raw by n8n) ----------------------------------------
@app.post("/api/shopify/webhook", dependencies=[Depends(require_token)])
async def shopify_webhook(request: Request, store: Store = Depends(get_store), s: Settings = Depends(get_settings),
                          x_shopify_hmac_sha256: str = Header(default=""), x_shopify_topic: str = Header(default="")):
    raw = await request.body()
    if not webhooks.verify_hmac(raw, x_shopify_hmac_sha256, s.shopify_webhook_secret):
        raise HTTPException(401, "invalid Shopify HMAC")
    payload = json.loads(raw)
    results = webhooks.handle(x_shopify_topic, payload, store)
    log.info("webhook %s: %s", x_shopify_topic, results)
    return {"topic": x_shopify_topic, "ergebnis": results}


@app.get("/api/report/daily", dependencies=[Depends(require_token)])
def daily_report(hours: int = 24, store: Store = Depends(get_store), s: Settings = Depends(get_settings)):
    return {**report.daily(store, hours=hours), "empfaenger": s.mail_to_daily, "absender": s.mail_from,
            "review_url": f"{s.review_base_url}/review/"}


@app.get("/api/mail-config", dependencies=[Depends(require_token)])
def mail_config(s: Settings = Depends(get_settings)):
    """Recipients for n8n mail nodes (n8n blocks env access in nodes)."""
    return {"from": s.mail_from, "daily": s.mail_to_daily, "alerts": s.mail_to_alerts or s.mail_to_daily}


EMPTY_PROPOSAL = {"titel": "", "untertitel": "", "ausgabe": "", "verlag": "", "jahr": None, "sprache": "",
                  "ean_isbn": "", "coverpreis": None, "waehrung": "", "format": "", "auffaelligkeiten": "",
                  "zustand_ki": None, "zustand_ki_begruendung": ""}


# --- review UI ------------------------------------------------------------------------
def _open_cases(store: Store) -> list[dict]:
    cases = []
    for obj in store.list_scans(EINGANG):
        tags = store.get_tags(obj.key)
        if tags.get("status") in ("offen", "fehler"):
            cases.append({"id": obj.copy_id, "status": tags["status"], "ki": tags.get("ki", ""),
                          "gescannt": obj.last_modified})
    cases.sort(key=lambda c: c["gescannt"])
    return cases


def _shop_cases(store: Store) -> list[dict]:
    """Copies already moved to aktiv/ (in Shopify), newest first, for the greyed-out list group."""
    objs = sorted(store.list_scans(AKTIV), key=lambda o: o.last_modified, reverse=True)[:SHOP_LIST_LIMIT]
    return [{"id": o.copy_id, "status": "aktiv", "ki": "", "gescannt": o.last_modified} for o in objs]


# Status tag -> label for the review UI (lifecycle in storage.py)
STATUS_LABELS = {
    "neu": "Neu",
    "in-arbeit": "Wird erkannt",
    "offen": "Zu prüfen",
    "bestaetigt": "Bestätigt, wartet auf Shop",
    "fehler": "Fehler",
    "aktiv": "Im Shop",
}
REVIEWABLE = ("offen", "fehler")
# Group order on the list page: work to do first, then what is still in the pipeline
GROUP_ORDER = ("offen", "fehler", "bestaetigt", "in-arbeit", "neu", "aktiv")
SHOP_LIST_LIMIT = 60  # copies already in the shop are shown greyed out, newest first (read-only)


def _inbox_cases(store: Store) -> list[dict]:
    """All scans still in eingang/, whatever their status, oldest first."""
    cases = []
    for obj in store.list_scans(EINGANG):
        tags = store.get_tags(obj.key)
        cases.append({"id": obj.copy_id, "status": tags.get("status", "neu"), "ki": tags.get("ki", ""),
                      "gescannt": obj.last_modified})
    cases.sort(key=lambda c: c["gescannt"])
    return cases


@app.get("/review", include_in_schema=False)
def review_root():
    return RedirectResponse("/review/", status_code=307)


@app.get("/review/", response_class=HTMLResponse, dependencies=[Depends(require_reviewer)])
def review_list(request: Request, store: Store = Depends(get_store)):
    cases = _inbox_cases(store) + _shop_cases(store)
    details = {}
    for c in cases:
        if c["status"] in ("offen", "bestaetigt", "aktiv"):
            try:
                side = store.read_json(store.sidecar_key(AKTIV if c["status"] == "aktiv" else EINGANG, c["id"]))
                details[c["id"]] = side.get("entscheidung") or side["vorschlag"]
            except (storage.NotFound, KeyError):
                pass
    open_count = sum(c["status"] in REVIEWABLE for c in cases)
    order = list(GROUP_ORDER) + sorted({c["status"] for c in cases} - set(GROUP_ORDER))
    groups = [(st, [c for c in cases if c["status"] == st]) for st in order]
    return templates.TemplateResponse(request, "liste.html", {
        "groups": [(st, cs) for st, cs in groups if cs], "details": details, "open_count": open_count,
        "labels": STATUS_LABELS, "reviewable": REVIEWABLE,
    })


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
UPLOAD_TYPES = ("image/jpeg", "image/png", "image/webp", "image/avif")
templates.env.globals["upload_typen"] = ",".join(UPLOAD_TYPES)


@app.get("/review/hochladen", response_class=HTMLResponse, dependencies=[Depends(require_reviewer)])
def upload_form(request: Request, fehler: str = ""):
    return templates.TemplateResponse(request, "hochladen.html", {"fehler": fehler})


@app.post("/review/hochladen", dependencies=[Depends(require_reviewer)])
def upload_photos(cover: UploadFile = File(...), rueckseite: UploadFile = File(...),
                  store: Store = Depends(get_store), s: Settings = Depends(get_settings)):
    """Second intake besides the scanner (ADR-0018): two photos -> eingang/{uuid}.pdf, status=neu."""
    def back(msg: str):
        return RedirectResponse(f"/review/hochladen?fehler={quote_plus(msg)}", status_code=303)

    images = []
    for name, f in (("Cover", cover), ("Rückseite", rueckseite)):
        data = f.file.read(MAX_UPLOAD_BYTES + 1)
        if not data:
            return back(f"{name} fehlt")
        if len(data) > MAX_UPLOAD_BYTES:
            return back(f"{name} ist größer als 25 MB")
        images.append(data)
    with _render_slot:
        try:
            scan = pdf.photos_to_scan_pdf(*images)
        except pdf.PdfError as e:
            return back(f"{e}. Erlaubt: JPEG, PNG, WebP, AVIF")
    copy_id = str(uuid.uuid4())
    store.put_new_scan(copy_id, scan)
    log.info("uploaded photos as %s (%d bytes)", copy_id, len(scan))
    _notify_n8n(s, copy_id, "scan-neu")  # start workflow 01 now instead of waiting for the 2-minute poll
    return RedirectResponse(f"/review/?hochgeladen={copy_id}", status_code=303)


@app.get("/review/bild/{copy_id}/{page}", dependencies=[Depends(require_reviewer)])
def review_image(copy_id: str, page: int, store: Store = Depends(get_store)):
    _check_id(copy_id)
    if page not in (1, 2):
        raise HTTPException(404)
    try:
        data = store.get_bytes(store.image_key(copy_id, page))
    except storage.NotFound:
        raise HTTPException(404)
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@app.get("/review/{copy_id}", response_class=HTMLResponse, dependencies=[Depends(require_reviewer)])
def review_form(copy_id: str, request: Request, store: Store = Depends(get_store), cfg: dict = Depends(get_cfg),
                fehler: str = ""):
    _check_id(copy_id)
    key = store.pdf_key(EINGANG, copy_id)
    if not store.exists(key):
        raise HTTPException(404, "Exemplar ist nicht (mehr) im Eingang")
    tags = store.get_tags(key)
    side_key = store.sidecar_key(EINGANG, copy_id)
    side = store.read_json(side_key) if store.exists(side_key) else {"id": copy_id}
    side.setdefault("ki_status", "nachkontrolle")
    side.setdefault("konfidenz", 0.0)
    side.setdefault("gescannt_am", "")
    side.setdefault("vorschlag", EMPTY_PROPOSAL)
    side.setdefault("preis_vorschlag", None)
    v = side.get("entscheidung") or side["vorschlag"]
    q = quote_plus(" ".join(x for x in (v.get("titel", ""), v.get("untertitel", "")) if x and x != "-"))
    links = {name: url.replace("{q}", q) for name, url in cfg["suchlinks"].items()}
    js_cfg = {
        "faktoren": {str(z): d["faktor"] for z, d in cfg["zustaende"].items()},
        "aufschlag": cfg["aufschlag"],
        "aufschlag_je_quelle": cfg.get("aufschlag_je_quelle") or {},
        "beleg_pflicht": cfg.get("beleg_pflicht") or [],
        "rundung": cfg["rundung"],
    }
    return templates.TemplateResponse(request, "review.html", {
        "id": copy_id, "side": side, "v": v, "tags": tags, "cfg": cfg, "links": links, "labels": STATUS_LABELS,
        "js_cfg": json.dumps(js_cfg), "fehler": fehler, "preis_vorschlag": side.get("preis_vorschlag"),
    })


@app.post("/review/{copy_id}/preis-suchen", dependencies=[Depends(require_reviewer)])
def review_search_price(copy_id: str, store: Store = Depends(get_store), cfg: dict = Depends(get_cfg),
                        s: Settings = Depends(get_settings), claude: anthropic.Anthropic = Depends(get_claude)):
    """Runs the automatic price search again for an open copy (ADR-0022)."""
    _check_id(copy_id)
    key = store.pdf_key(EINGANG, copy_id)
    side_key = store.sidecar_key(EINGANG, copy_id)
    if not store.exists(key) or not store.exists(side_key):
        raise HTTPException(404)
    if store.get_tags(key).get("status") not in REVIEWABLE:
        raise HTTPException(409, "Nur offene oder fehlerhafte Exemplare")
    side = store.read_json(side_key)
    hint = marktpreis.suggest(claude, side["vorschlag"], cfg, s.anthropic_model)
    if hint is None:
        return RedirectResponse(f"/review/{copy_id}?fehler=" + quote_plus(
            "Keine passenden Angebote gefunden. Bitte von Hand über die Links suchen."), status_code=303)
    side["preis_vorschlag"] = hint
    side["preis_suche"] = _utc()
    store.write_json(side_key, side)
    return RedirectResponse(f"/review/{copy_id}", status_code=303)


@app.post("/review/{copy_id}/neu-erkennen", dependencies=[Depends(require_reviewer)])
def review_retry(copy_id: str, store: Store = Depends(get_store)):
    """Puts a failed scan back into the queue; n8n picks it up on the next run."""
    _check_id(copy_id)
    key = store.pdf_key(EINGANG, copy_id)
    if not store.exists(key):
        raise HTTPException(404)
    store.update_tags(key, status="neu", claimed=None)
    return RedirectResponse("/review/", status_code=303)


@app.post("/review/{copy_id}/loeschen", dependencies=[Depends(require_reviewer)])
def review_delete(copy_id: str, store: Store = Depends(get_store)):
    """Moves a reviewable copy to papierkorb/ (ADR-0019); nothing is deleted for good."""
    _check_id(copy_id)
    key = store.pdf_key(EINGANG, copy_id)
    if not store.exists(key):
        raise HTTPException(404)
    if store.get_tags(key).get("status") not in REVIEWABLE:
        raise HTTPException(409, "Nur offene oder fehlerhafte Exemplare können gelöscht werden")
    store.move(copy_id, EINGANG, storage.PAPIERKORB, tags={"status": "geloescht", "geloescht": str(int(time.time()))})
    log.info("moved %s to %s/", copy_id, storage.PAPIERKORB)
    return RedirectResponse(f"/review/?geloescht={copy_id}", status_code=303)


@app.post("/review/{copy_id}/zurueckholen", dependencies=[Depends(require_reviewer)])
def review_reopen(copy_id: str, store: Store = Depends(get_store)):
    """Takes a confirmation back while the copy is not yet in Shopify (ADR-0020); the decision stays as prefill."""
    _check_id(copy_id)
    key = store.pdf_key(EINGANG, copy_id)
    if not store.exists(key):
        raise HTTPException(404, "Exemplar ist nicht (mehr) im Eingang")
    if store.get_tags(key).get("status") != "bestaetigt":
        raise HTTPException(409, "Nur bestätigte Exemplare können zurückgeholt werden")
    side_key = store.sidecar_key(EINGANG, copy_id)
    if store.exists(side_key) and store.read_json(side_key).get("shopify"):
        raise HTTPException(409, "Schon in Shopify angelegt")
    store.update_tags(key, status="offen")
    log.info("reopened %s", copy_id)
    return RedirectResponse(f"/review/{copy_id}", status_code=303)


def _notify_n8n(s: Settings, copy_id: str, hook: str = "comic-bestaetigt") -> None:
    """Best effort: n8n also polls (confirmed comics every 15 min, new scans every 2 min), so a failure
    here loses nothing."""
    try:
        httpx2.post(f"{s.n8n_internal_url}/webhook/{hook}", json={"id": copy_id},
                    headers={"X-Helper-Token": s.helper_token}, timeout=10)
    except httpx2.HTTPError as e:
        log.warning("n8n notify (%s) failed for %s: %s", hook, copy_id, e)


@app.post("/review/{copy_id}", dependencies=[Depends(require_reviewer)])
def review_submit(
    copy_id: str,
    store: Store = Depends(get_store),
    cfg: dict = Depends(get_cfg),
    s: Settings = Depends(get_settings),
    titel: str = Form(...),
    untertitel: str = Form(""),
    ausgabe: str = Form(""),
    verlag: str = Form(""),
    jahr: str = Form(""),
    sprache: str = Form(""),
    ean_isbn: str = Form(""),
    format: str = Form(""),
    zustand: int = Form(...),
    basis_z1: str = Form(""),
    preisquelle: str = Form(...),
    preis_override: str = Form(""),
    preis_beleg: str = Form(""),
    notiz: str = Form(""),
):
    _check_id(copy_id)
    key = store.pdf_key(EINGANG, copy_id)
    if not store.exists(key):
        raise HTTPException(404)
    if store.get_tags(key).get("status") not in ("offen", "fehler"):
        raise HTTPException(409, "Exemplar wurde bereits bestätigt")

    def back(msg: str):
        return RedirectResponse(f"/review/{copy_id}?fehler={quote_plus(msg)}", status_code=303)

    def money(x: str) -> float | None:
        x = x.strip().replace("€", "").replace(",", ".")
        return float(x) if x else None

    try:
        basis = money(basis_z1)
        override = money(preis_override)
    except ValueError:
        return back("Preis bitte als Zahl eingeben, z. B. 12,50")
    if not titel.strip():
        return back("Titel fehlt")
    if basis is None:
        return back("Zustand-1-Preis fehlt (Booklooker, Comicguide, Katalog oder Coverpreis)")
    try:
        price = pricing.calculate(basis, zustand, preisquelle, cfg).as_dict()
    except ValueError as e:
        return back(str(e))
    beleg = preis_beleg.strip()
    if beleg and not beleg.startswith(("https://", "http://")):
        return back("Beleg bitte als Link angeben (https://…)")
    if len(beleg) > 300:
        return back("Beleg-Link ist zu lang (max. 300 Zeichen)")
    if not beleg and preisquelle in (cfg.get("beleg_pflicht") or []):
        return back(f"Beleg fehlt: Link auf das {preisquelle}-Angebot eintragen")
    if beleg:
        price["beleg"] = beleg
    if override is not None:
        if override <= 0:
            return back("Überschriebener Preis muss größer 0 sein")
        price.update(final=round(override, 2), ueberschrieben=True)

    side_key = store.sidecar_key(EINGANG, copy_id)
    side = store.read_json(side_key) if store.exists(side_key) else {"id": copy_id}
    side.setdefault("vorschlag", EMPTY_PROPOSAL)
    side["entscheidung"] = {
        "titel": titel.strip(), "untertitel": untertitel.strip(), "ausgabe": ausgabe.strip() or "-",
        "verlag": verlag.strip(), "jahr": int(jahr) if jahr.strip().isdigit() else None,
        "sprache": sprache.strip().lower(), "ean_isbn": ean_isbn.strip(), "format": format.strip(),
        "zustand": zustand, "preis": price, "notiz": notiz.strip()[:2000], "am": _utc(),
        "korrigiert": any(
            (str(side["vorschlag"].get(f) or "") != str(val).strip())
            for f, val in (("titel", titel), ("ausgabe", ausgabe), ("verlag", verlag))
        ),
        "sku_vorschau": make_sku(titel.strip(), ausgabe.strip(), zustand, storage.short_id(copy_id)),
    }
    store.write_json(side_key, side)
    store.update_tags(key, status="bestaetigt")
    _notify_n8n(s, copy_id)

    nxt = next((c["id"] for c in _open_cases(store) if c["status"] == "offen" and c["id"] != copy_id), None)
    return RedirectResponse(f"/review/{nxt}" if nxt else "/review/?fertig=1", status_code=303)
