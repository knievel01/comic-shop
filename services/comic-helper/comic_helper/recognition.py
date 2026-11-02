"""Comic recognition with Claude (vision + structured output).

Reads title, issue, publisher, year, language, EAN/ISBN and printed cover price from the
cover and back scans. Unreadable fields stay empty - nothing is guessed.
"""

from __future__ import annotations

import base64
import re
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

# Models that accept server-side refusal fallbacks (fallbacks="default")
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """\
Du erfasst Comics für den Ankauf/Verkauf in einem deutschen Comic-Antiquariat.
Du bekommst zwei Scans desselben Exemplars: Seite 1 ist das Cover, Seite 2 die Rückseite.
Die Sammlung enthält deutsche Hefte und Alben (z. B. Ehapa, Carlsen, Bastei, Condor, Panini),
US-Comics und Manga aus allen Jahrzehnten seit 1945.

Regeln:
- Erfasse nur, was auf den Scans steht oder sich eindeutig aus Gedrucktem ergibt
  (z. B. Verlagslogo). Nichts raten und kein Wissen ergänzen, das nicht belegt ist.
- Nicht lesbare oder nicht vorhandene Angaben: wert = null, sicherheit = 0.
- sicherheit ist deine Einschätzung von 0.0 bis 1.0, dass der Wert exakt stimmt.
- titel: Serien- bzw. Reihentitel, wie gedruckt (z. B. "Asterix", "Micky Maus", "Fix und Foxi").
- untertitel: Titel des einzelnen Bandes/der Geschichte, falls vorhanden.
- ausgabe: Heft- bzw. Bandnummer nur als arabische Zahl, ohne Wörter (z. B. "12"; bei Jahrgang
  und Heft "1987/23"). Römische oder ausgeschriebene Zahlen übersetzen ("II" und "Zwei" werden "2").
  Zusätze wie "Band", "Nr.", "Sonderheft", "Großer Sonderband" gehören nicht in ausgabe, sondern
  in auffaelligkeiten. Hat das Exemplar sichtbar keine Nummer, wert = "-" mit entsprechender Sicherheit.
- jahr: Erscheinungsjahr (vierstellig), nur wenn gedruckt oder eindeutig ableitbar.
- sprache: ISO-639-1-Code der Sprache des Comics (de, en, fr, ja, ...).
- ean_isbn: nur Ziffern (und ggf. X), ohne Bindestriche; vom Barcode oder ISBN-Aufdruck.
- coverpreis: der aufgedruckte Preis als Dezimalzahl mit Punkt (z. B. "6.99").
  waehrung: ISO-Code (EUR, DEM, ATS, CHF, USD, ...). "DM" ist DEM, "öS" ist ATS.
  Gibt es mehrere Preise (z. B. D/A/CH), nimm den deutschen.
- format: Heft, Album, Taschenbuch, Manga oder Sonstiges.
- auffaelligkeiten: kurze sachliche Notiz zu sichtbaren Schäden, Stempeln, fehlenden Teilen
  oder Besonderheiten (Erstauflage, Beilage). Leer, wenn nichts auffällt.
- zustand_empfehlung: Empfehlung für die Zustandsstufe nach der Skala unten (nur ganze Stufen),
  allein nach dem, was auf den Bildern sichtbar ist. Fehlt eine echte Rückseite oder ist der Zustand
  nicht beurteilbar, null. Die Fachkraft entscheidet am Exemplar; die Empfehlung ist nur ein Hinweis.
- zustand_begruendung: ein Satz mit den sichtbaren Merkmalen, auf die sich die Empfehlung stützt.
"""

CONDITION_SCALE_HEADER = "\nZustandsskala (Comicguide-Stufen):\n"


class Feld(BaseModel):
    wert: str | None = Field(description="Wert wie gelesen, oder null")
    sicherheit: float = Field(description="0.0 bis 1.0")


class Erkennung(BaseModel):
    titel: Feld
    untertitel: Feld
    ausgabe: Feld
    verlag: Feld
    jahr: Feld
    sprache: Feld
    ean_isbn: Feld
    coverpreis: Feld
    waehrung: Feld
    format: Feld
    auffaelligkeiten: str | None
    zustand_empfehlung: int | None = Field(description="0 bis 4 oder null")
    zustand_begruendung: str | None


class RecognitionError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def _image_block(jpeg: bytes) -> dict:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.standard_b64encode(jpeg).decode()},
    }


def system_prompt(zustaende: dict | None = None) -> str:
    """Rules plus the condition scale from config/pricing.yaml (single source, ADR-0011)."""
    if not zustaende:
        return SYSTEM_PROMPT
    scale = "".join(f"- {z} {d['bezeichnung']}: {d['hilfe']}\n" for z, d in sorted(zustaende.items()))
    return SYSTEM_PROMPT + CONDITION_SCALE_HEADER + scale


def recognize(client: anthropic.Anthropic, cover_jpeg: bytes, back_jpeg: bytes, model: str, effort: str = "low",
              zustaende: dict | None = None) -> tuple[Erkennung, dict]:
    """Returns (parsed result, usage/model info). Raises RecognitionError."""
    extra = {}
    if model in FALLBACK_MODELS:
        extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"}
    try:
        response = client.beta.messages.parse(
            model=model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            system=system_prompt(zustaende),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Seite 1 – Cover:"},
                    _image_block(cover_jpeg),
                    {"type": "text", "text": "Seite 2 – Rückseite:"},
                    _image_block(back_jpeg),
                    {"type": "text", "text": "Erfasse die Angaben zu diesem Comic."},
                ],
            }],
            output_format=Erkennung,
            **extra,
        )
    except anthropic.RateLimitError as e:
        raise RecognitionError(f"rate limited: {e}", retryable=True) from e
    except anthropic.InternalServerError as e:
        raise RecognitionError(f"Claude API error {e.status_code}", retryable=True) from e
    except anthropic.APIStatusError as e:
        raise RecognitionError(f"Claude API error {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise RecognitionError(f"Claude API not reachable: {e}", retryable=True) from e

    if response.stop_reason == "refusal":
        raise RecognitionError("Claude declined the request (refusal)")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RecognitionError(f"no structured result (stop_reason={response.stop_reason})", retryable=True)

    info = {
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return response.parsed_output, info


def overall_confidence(e: Erkennung) -> float:
    """Copy is 'sicher' only if title, issue and publisher are all confidently read."""
    return round(min(e.titel.sicherheit, e.ausgabe.sicherheit, e.verlag.sicherheit), 3)


def classify(confidence: float, threshold: float) -> Literal["sicher", "nachkontrolle"]:
    return "sicher" if confidence >= threshold else "nachkontrolle"


_ROMAN = re.compile(r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})")
_ROMAN_VALUES = {"M": 1000, "D": 500, "C": 100, "L": 50, "X": 10, "V": 5, "I": 1}
_ISSUE_TOKEN = re.compile(r"\d+(?:/\d+)?|\b[IVXLCDM]+\b")


def _roman_to_int(numeral: str) -> int:
    total = 0
    for ch, nxt in zip(numeral, numeral[1:] + " "):
        value = _ROMAN_VALUES[ch]
        total += -value if nxt != " " and _ROMAN_VALUES[nxt] > value else value
    return total


def normalize_issue(value: str) -> str:
    """Reduce an issue to a plain number ("Grosser Sonderband II" -> "2", "Nr. 012" -> "12").

    Keeps year/issue ("1987/23") and "-" (no number). Ambiguous values (several or no
    numbers) are returned unchanged for the reviewer.
    """
    value = value.strip()
    tokens = [t for t in _ISSUE_TOKEN.findall(value) if t[0].isdigit() or _ROMAN.fullmatch(t)]
    if value in ("", "-") or len(tokens) != 1:
        return value
    token = tokens[0]
    if token[0].isdigit():
        return "/".join(str(int(part)) for part in token.split("/"))
    return str(_roman_to_int(token))


def to_proposal(e: Erkennung) -> dict:
    """Flat dict for the review form."""
    def v(f: Feld) -> str:
        return (f.wert or "").strip()

    price = None
    try:
        price = float(v(e.coverpreis).replace(",", ".")) if v(e.coverpreis) else None
    except ValueError:
        price = None
    year = None
    if v(e.jahr)[:4].isdigit():
        year = int(v(e.jahr)[:4])
    return {
        "titel": v(e.titel),
        "untertitel": v(e.untertitel),
        "ausgabe": normalize_issue(v(e.ausgabe)),
        "verlag": v(e.verlag),
        "jahr": year,
        "sprache": v(e.sprache).lower(),
        "ean_isbn": "".join(ch for ch in v(e.ean_isbn) if ch.isdigit() or ch in "xX"),
        "coverpreis": price,
        "waehrung": v(e.waehrung).upper(),
        "format": v(e.format),
        "auffaelligkeiten": (e.auffaelligkeiten or "").strip(),
        "zustand_ki": e.zustand_empfehlung if e.zustand_empfehlung in (0, 1, 2, 3, 4) else None,
        "zustand_ki_begruendung": (e.zustand_begruendung or "").strip() if e.zustand_empfehlung in (0, 1, 2, 3, 4) else "",
    }
