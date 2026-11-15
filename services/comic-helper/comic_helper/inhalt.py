"""Short, spoiler-free content text per comic for the shop (ADR-0010).

Written from the back-cover scan (in own words) or from safe knowledge of the exact issue; empty otherwise.
No web search, no copying of publisher or catalogue texts (ADR-0011). Best effort: a failure or an empty
result never blocks recognition - the reviewer can write the text by hand.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from .recognition import FALLBACK_BETA, FALLBACK_MODELS, _image_block

log = logging.getLogger("comic_helper.inhalt")

PROMPT = """\
Schreibe einen kurzen Inhaltstext für den Online-Shop eines deutschen Comic-Antiquariats.

Heft:
Titel: {titel}
Untertitel: {untertitel}
Ausgabe/Nummer: {ausgabe}
Verlag: {verlag}

Quellen, in dieser Reihenfolge:
1. Steht auf der Rückseite (Bild, falls beigelegt) ein Text zur Handlung, fasse ihn in eigenen Worten
   zusammen. Übernimm keinen Satz und keine auffällige Wendung wörtlich (quelle = "rueckseite").
2. Sonst: nur wenn du genau diesen Band sicher kennst, schreibe aus deinem Wissen (quelle = "wissen").
3. Sonst: text = null und quelle = "keine". Im Zweifel leer lassen. Ein falscher Text ist schlimmer als keiner.

Ton und Form:
- Deutsch, locker und warm, wie ein Comic-Händler, der einem Stammkunden vom Heft erzählt. Direkte Anrede
  ("du") ist erlaubt.
- 2 bis 4 Sätze, höchstens {max_zeichen} Zeichen, spoilerfrei: nenne Ausgangslage und Reiz, nicht das Ende.
- Keine Wertung wie "bestes Heft", keine Aussagen zu Preis, Zustand, Seltenheit oder Sammlerwert.
- Bleib bei dem, was belegt ist, und nichts erfinden: keine Jahreszahlen, Autoren, Zeichner oder Figuren, die nicht belegt sind.
- Reiner Text: kein HTML, keine Links, keine Aufzählung, keine Überschrift.

sicherheit ist deine Einschätzung von 0.0 bis 1.0, dass der Text inhaltlich zu genau diesem Heft stimmt.
"""


class InhaltErgebnis(BaseModel):
    text: str | None = Field(description="Inhaltstext oder null")
    quelle: Literal["rueckseite", "wissen", "keine"]
    sicherheit: float = Field(description="0.0 bis 1.0")


_MARKUP = re.compile(r"<[^>]*>|&\w+;|&#\d+;|https?://|www\.", re.IGNORECASE)


def prompt(proposal: dict, cfg: dict) -> str:
    return PROMPT.format(titel=proposal.get("titel") or "-", untertitel=proposal.get("untertitel") or "-",
                         ausgabe=proposal.get("ausgabe") or "-", verlag=proposal.get("verlag") or "-",
                         max_zeichen=int(cfg["inhalt"]["max_zeichen"]))


def bereinigen(e: InhaltErgebnis, cfg: dict) -> dict | None:
    """Apply the acceptance rules; None means 'no usable text'."""
    c = cfg["inhalt"]
    text = (e.text or "").strip()
    if e.quelle == "keine" or not text:
        return None
    if e.sicherheit < float(c["schwelle"]) or len(text) > int(c["max_zeichen"]) or _MARKUP.search(text):
        return None
    return {"text": text, "quelle": e.quelle, "sicherheit": round(e.sicherheit, 3)}


def schreibe(client: anthropic.Anthropic, proposal: dict, back_jpeg: bytes | None, model: str, effort: str,
             cfg: dict, usage_out: dict | None = None) -> dict | None:
    """Returns {"text", "quelle", "sicherheit"} or None. Never raises; errors go to the log and usage_out."""
    usage = usage_out if usage_out is not None else {}
    usage.update({"model": model, "input_tokens": 0, "output_tokens": 0})
    t0 = time.monotonic()
    content: list[dict] = []
    if back_jpeg:
        content += [{"type": "text", "text": "Rückseite des Hefts:"}, _image_block(back_jpeg)]
    content.append({"type": "text", "text": prompt(proposal, cfg)})
    extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"} if model in FALLBACK_MODELS else {}
    try:
        response = client.beta.messages.parse(
            model=model, max_tokens=4000, output_config={"effort": effort},
            messages=[{"role": "user", "content": content}], output_format=InhaltErgebnis, **extra)
        usage["model"] = response.model or model
        usage["input_tokens"] = response.usage.input_tokens
        usage["output_tokens"] = response.usage.output_tokens
        if response.stop_reason in ("refusal", "max_tokens") or response.parsed_output is None:
            usage["fehler"] = f"kein Ergebnis (stop_reason={response.stop_reason})"
            return None
        return bereinigen(response.parsed_output, cfg)
    except Exception as e:  # best effort: the reviewer can always write the text by hand
        usage["fehler"] = str(e) or type(e).__name__
        log.warning("content text failed: %s", usage["fehler"])
        return None
    finally:
        usage["seconds"] = round(time.monotonic() - t0, 1)
