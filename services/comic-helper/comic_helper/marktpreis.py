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
Ermittle aktuelle Gebrauchtpreise für genau dieses Comic. Du hast nur die Websuche, sie ist auf
Booklooker (booklooker.de) und ZVAB (zvab.com) beschränkt.

Titel: {titel}
Untertitel: {untertitel}
Ausgabe/Nummer: {ausgabe}
Verlag: {verlag}
Jahr: {jahr}
Sprache: {sprache}
EAN/ISBN: {ean}

Vorgehen:
1. Händler führen einen Band meist unter seinem Bandtitel, nicht unter der Nummer (Asterix 5 heißt
   "Die goldene Sichel"). Überlege dir den Bandtitel und suche damit plus Reihe, Nummer und Verlag.
2. Suche höchstens 4-mal mit kurzen Anfragen in normalem Deutsch, ohne Operatoren und ohne
   Anführungszeichen, z. B. "Asterix Die goldene Sichel Band 5 Ehapa gebraucht Booklooker" und
   danach dieselbe Anfrage mit "ZVAB". Ist eine EAN/ISBN angegeben, ist eine Suche damit sinnvoll.
   Wiederhole keine Anfrage.
3. Eine Trefferliste zeigt meist mehrere Angebote mit Preis. Lies sie ganz und sammle 5 bis 8
   passende Angebote, möglichst von beiden Portalen. Hast du erst 1 oder 2, suche mit anderem
   Wortlaut weiter, bevor du antwortest. Wähle nicht nach Preis aus: nimm die passenden Angebote in
   der Reihenfolge der Trefferliste, auch wenn sie sehr billig oder sehr teuer sind.

Ein Angebot zählt nur, wenn alles zutrifft:
- Gleicher Band: gleiche Nummer bzw. gleicher Bandtitel, deutsche Ausgabe.
- Gleicher Verlag wie oben angegeben. Schreibvarianten und Namenswechsel desselben Hauses zählen
  mit (z. B. Ehapa und Egmont Ehapa); fremde Verlage und Ausgaben aus anderen Ländern nicht. Fehlt
  die Verlagsangabe, genügt die deutsche Ausgabe.
- Einzelband bzw. Einzelheft: kein Sammelband, keine Gesamtausgabe, kein Set, Konvolut, Poster, Hörspiel
  oder E-Book.
- Gebrauchtes Exemplar in gutem bis sehr gutem Zustand (leichte Gebrauchsspuren sind in Ordnung).
  Nicht: "neu", beschädigt, stark bestoßen, Wasserschaden, fehlende Seiten, Mängel.
- Der Preis steht als Zahl in Euro in der Fundstelle, ohne Versand. Du schätzt, rechnest oder ergänzt
  nichts. Ohne belegten Preis gibt es kein Angebot.

Angaben je Angebot:
- preis: die Zahl mit Punkt, z. B. 6.5
- beschreibung: höchstens 100 Zeichen, so wie in der Fundstelle: Verlag, Jahr, Einband, Zustand
- url: die Adresse der Angebots- oder Trefferseite aus der Suche, auf der du den Preis gesehen hast.
  Erfinde oder verändere keine Adresse.

Schreibe keine Zwischenschritte und keine Begründung. Deine letzte Nachricht besteht nur aus diesem
JSON, bei keinem passenden Angebot mit leerer Liste:
{{"angebote": [{{"preis": 6.5, "beschreibung": "Ehapa, 1980, Softcover, Zustand gut", "url": "https://..."}}]}}
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


def _find_answer(text: str) -> dict | None:
    """Last JSON object with an "angebote" key. Weaker models may add prose, code fences or draft answers."""
    decoder = json.JSONDecoder()
    found = None
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text, m.start())
        except ValueError:
            continue
        if isinstance(obj, dict) and "angebote" in obj:
            found = obj
    return found


def parse_offers(text: str) -> list[Angebot]:
    """Extract the JSON object from the final answer; keep only offers from our two portals."""
    answer = _find_answer(text)
    raw = answer.get("angebote", []) if answer else []
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
