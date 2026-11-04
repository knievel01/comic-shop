"""Automatic price suggestion from used-book offers on Booklooker and ZVAB (ADR-0022).

The search is done by Anthropic's web search tool, not by this service: we never request
booklooker.de or zvab.com ourselves (their robots.txt blocks programs, ADR-0017). Claude only
reports offers it literally found (price, link); the median and the explanation are computed here.
A failed or empty search never blocks recognition - the reviewer then enters the price by hand.
"""

from __future__ import annotations

import json
import logging
import re
import statistics
import time
from datetime import date
from urllib.parse import urlparse

import anthropic
from pydantic import BaseModel, Field, ValidationError

log = logging.getLogger("comic_helper.marktpreis")

PORTALS = {"booklooker.de": "Booklooker", "zvab.com": "ZVAB"}

PROMPT = """\
Suche mit der Websuche aktuelle Angebote für genau dieses Comic bei Booklooker (booklooker.de) und
ZVAB (zvab.com):

Titel: {titel}
Untertitel: {untertitel}
Ausgabe/Nummer: {ausgabe}
Verlag: {verlag}
Jahr: {jahr}
Sprache: {sprache}
EAN/ISBN: {ean}

Regeln:
- Nimm nur Angebote derselben Ausgabe (gleiche Nummer, möglichst gleicher Verlag, Originalausgabe,
  keine Neuauflage und kein Sammelband, wenn das Heft ein Einzelheft ist).
- Nimm nur gebrauchte Exemplare in unauffälligem Zustand (gut bis sehr gut erhalten). Keine
  Angebote mit Mängeln, keine "neu"-Angebote, keine Sets oder Konvolute.
- Preis in Euro ohne Versand, genau so, wie er in der Fundstelle steht. Keine Preise schätzen,
  umrechnen oder ergänzen. Ohne belegbaren Preis kein Angebot.
- url ist die Seite des Angebots oder der Trefferliste, in der du den Preis gesehen hast.
- Findest du nichts Passendes, gib eine leere Liste zurück. Mehr als 8 Angebote sind nicht nötig.

Antworte zuletzt nur mit JSON in diesem Format, ohne weiteren Text:
{{"angebote": [{{"preis": 6.5, "beschreibung": "Kurzbeschreibung der Fundstelle", "url": "https://..."}}]}}
"""


class Angebot(BaseModel):
    preis: float = Field(gt=0)
    beschreibung: str = ""
    url: str


def portal_of(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    for domain, name in PORTALS.items():
        if host == domain or host.endswith("." + domain):
            return name
    return None


def parse_offers(text: str) -> list[Angebot]:
    """Extract the JSON object from the final answer; keep only offers from our two portals."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return []
    try:
        raw = json.loads(match.group(0)).get("angebote", [])
    except (ValueError, AttributeError):
        return []
    seen: set[tuple[float, str]] = set()
    out = []
    for item in raw if isinstance(raw, list) else []:
        try:
            o = Angebot.model_validate(item)  # one bad entry must not discard the others
        except ValidationError:
            continue
        if portal_of(o.url) is None or (o.preis, o.url) in seen:
            continue
        seen.add((o.preis, o.url))
        out.append(o)
    return out


def _fmt(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def build_suggestion(offers: list[Angebot], cfg: dict, today: date | None = None) -> dict | None:
    """Median of the offers -> price suggestion with the explanation. None if too few offers."""
    conf = cfg.get("marktpreis") or {}
    if len(offers) < int(conf.get("min_angebote", 2)):
        return None
    prices = sorted(o.preis for o in offers)
    median = round(statistics.median(prices), 2)
    nearest = min(offers, key=lambda o: (abs(o.preis - median), o.preis))
    count = {}
    for o in offers:
        count[portal_of(o.url)] = count.get(portal_of(o.url), 0) + 1
    where = ", ".join(f"{n} bei {p}" for p, n in sorted(count.items()))
    today = today or date.today()
    lines = [
        f"Automatischer Preisvorschlag vom {today.strftime('%d.%m.%Y')}: Median von {len(offers)} Angeboten "
        f"({where}) = {_fmt(median)} €.",
        "Gefundene Preise: " + " · ".join(_fmt(p) for p in prices) + " € (ohne Versand).",
        "So entstanden: Websuche nach Titel, Ausgabe und Verlag bei Booklooker und ZVAB; gesucht sind gebrauchte "
        "Exemplare derselben Ausgabe; der mittlere Wert (Median), damit einzelne Ausreißer nicht zählen. "
        "Angebotspreise sind keine Verkaufspreise, Zustand und Ausgabe bitte am Beleg prüfen.",
        "Angebote:",
        *[f"- {_fmt(o.preis)} € {portal_of(o.url)}: {o.url}" + (f" ({o.beschreibung})" if o.beschreibung else "")
          for o in sorted(offers, key=lambda o: o.preis)],
    ]
    return {
        "basis_z1": median,
        "quelle": "booklooker",
        "beleg": nearest.url[:300],
        "hinweis": f"Median von {len(offers)} Angeboten ({where}), Spanne {_fmt(prices[0])} bis {_fmt(prices[-1])} €.",
        "notiz": "\n".join(lines),
        "angebote": [o.model_dump() for o in offers],
    }


def suggest(client: anthropic.Anthropic, proposal: dict, cfg: dict, model: str,
            usage_out: dict | None = None) -> dict | None:
    """Search offers and build the suggestion. Returns None on any problem (logged).

    `marktpreis.modell` in pricing.yaml overrides `model`. Token and search counts are logged and, if
    given, summed into `usage_out` (used by scripts/preissuche-vergleich.py).
    """
    conf = cfg.get("marktpreis") or {}
    model = conf.get("modell") or model
    usage = usage_out if usage_out is not None else {}
    usage.update(model=model, input_tokens=0, output_tokens=0, searches=0, attempts=0, seconds=0.0)
    started = time.monotonic()
    if not conf.get("aktiv", False) or not proposal.get("titel") or proposal["titel"] == "-":
        return None
    ean = proposal.get("ean_isbn") or ""
    prompt = PROMPT.format(
        titel=proposal["titel"], untertitel=proposal.get("untertitel") or "-", ausgabe=proposal.get("ausgabe") or "-",
        verlag=proposal.get("verlag") or "-", jahr=proposal.get("jahr") or "-", sprache=proposal.get("sprache") or "-",
        ean=ean if len(ean) in (10, 13) else "-")  # misread barcodes would only mislead the search
    attempts = int(conf.get("versuche", 2))
    offers: list[Angebot] = []
    for attempt in range(1, attempts + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=int(conf.get("max_tokens", 4000)),
                tools=[{"type": "web_search_20250305", "name": "web_search",
                        "max_uses": int(conf.get("max_suchen", 4)),
                        "allowed_domains": list(PORTALS)}],
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as e:
            log.warning("price search failed (attempt %d): %s", attempt, e)
            continue
        text = "".join(b.text for b in response.content if b.type == "text")
        offers = parse_offers(text)
        u = response.usage
        usage["attempts"] += 1
        usage["input_tokens"] += u.input_tokens
        usage["output_tokens"] += u.output_tokens
        usage["searches"] += getattr(getattr(u, "server_tool_use", None), "web_search_requests", 0) or 0
        usage["seconds"] = round(time.monotonic() - started, 1)
        log.info("price search for %r #%s (attempt %d, %s): %d offers, %d in / %d out tokens, %d searches, %.1fs",
                 proposal["titel"], proposal.get("ausgabe"), attempt, model, len(offers), u.input_tokens,
                 u.output_tokens, getattr(getattr(u, "server_tool_use", None), "web_search_requests", 0) or 0,
                 usage["seconds"])
        if len(offers) >= int(conf.get("min_angebote", 2)):
            break
        log.info("price search answer without usable offers: %s", text[:500].replace("\n", " "))
    usage["seconds"] = round(time.monotonic() - started, 1)
    return build_suggestion(offers, cfg)
