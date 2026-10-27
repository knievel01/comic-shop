#!/usr/bin/env python3
"""Phase 6.1 – comparison test of the recognition (Claude vs. Ximilar).

Input: a folder of 2-page PDFs and a CSV with the ground truth, one row per PDF:

    datei;titel;ausgabe;verlag;deutsch;ximilar
    asterix12.pdf;Asterix;12;Ehapa;j;nicht
    spiderman300.pdf;The Amazing Spider-Man;300;Marvel;n;richtig

`ximilar` is filled in by hand from the Ximilar demo/API (richtig | falsch | nicht).
The script runs the Claude recognition used in production on every PDF and writes
<csv>-ergebnis.csv plus a summary per path and per German/non-German share.

Usage (needs ANTHROPIC_API_KEY, poppler-utils):
    python3 scripts/vergleichstest.py testdaten/vergleich.csv [--model claude-opus-5-5] [--effort low]
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "comic-helper"))

import anthropic  # noqa: E402

from comic_helper import pdf, recognition  # noqa: E402


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()
    return "".join(ch for ch in s if ch.isalnum())


def verdict(truth: dict, got: dict) -> str:
    if not got.get("titel"):
        return "nicht"
    same = (norm(truth["titel"]) in norm(got["titel"]) or norm(got["titel"]) in norm(truth["titel"])) \
        and norm(truth["ausgabe"]) == norm(got["ausgabe"]) \
        and (not truth.get("verlag") or norm(truth["verlag"]) in norm(got["verlag"]) or norm(got["verlag"]) in norm(truth["verlag"]))
    return "richtig" if same else "falsch"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--effort", default="low")
    ap.add_argument("--schwelle", type=float, default=0.80)
    args = ap.parse_args()

    rows = list(csv.DictReader(args.csv.open(encoding="utf-8"), delimiter=";"))
    client = anthropic.Anthropic()
    out_rows, tokens = [], Counter()
    for row in rows:
        path = args.csv.parent / row["datei"]
        got, conf, err = {}, 0.0, ""
        try:
            pages = pdf.render_pages(path.read_bytes())
            res, info = recognition.recognize(
                client, pdf.to_jpeg(pages[0], pdf.MODEL_MAX_EDGE), pdf.to_jpeg(pages[1], pdf.MODEL_MAX_EDGE),
                model=args.model, effort=args.effort)
            got, conf = recognition.to_proposal(res), recognition.overall_confidence(res)
            tokens.update(input=info["input_tokens"], output=info["output_tokens"])
        except Exception as e:  # keep going, record the error
            err = str(e)
        v = verdict(row, got)
        out_rows.append({
            **row,
            "claude": v,
            "claude_titel": got.get("titel", ""), "claude_ausgabe": got.get("ausgabe", ""),
            "claude_verlag": got.get("verlag", ""), "claude_konfidenz": conf,
            "claude_einstufung": recognition.classify(conf, args.schwelle) if got else "",
            "fehler": err,
        })
        print(f"{row['datei']:40} claude={v:8} ximilar={row.get('ximilar', ''):8} {conf:.2f} {err}")

    out = args.csv.with_name(args.csv.stem + "-ergebnis.csv")
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(out_rows)

    def summary(subset, label):
        if not subset:
            return
        c, x = Counter(r["claude"] for r in subset), Counter(r.get("ximilar", "") for r in subset)
        sure = [r for r in subset if r["claude_einstufung"] == "sicher"]
        sure_ok = sum(r["claude"] == "richtig" for r in sure)
        print(f"\n{label} ({len(subset)} Comics)")
        print(f"  Claude : richtig {c['richtig']:3}  falsch {c['falsch']:3}  nicht {c['nicht']:3}")
        print(f"  Ximilar: richtig {x['richtig']:3}  falsch {x['falsch']:3}  nicht {x['nicht']:3}")
        if sure:
            print(f"  Claude 'sicher' eingestuft: {len(sure)}, davon richtig {sure_ok} ({sure_ok / len(sure):.0%})")

    summary(out_rows, "Gesamt")
    summary([r for r in out_rows if r.get("deutsch", "").lower().startswith("j")], "Deutsch")
    summary([r for r in out_rows if not r.get("deutsch", "").lower().startswith("j")], "Nicht deutsch")
    print(f"\nTokens: {tokens['input']} input, {tokens['output']} output ({args.model}, effort {args.effort})")
    print(f"Ergebnis: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
