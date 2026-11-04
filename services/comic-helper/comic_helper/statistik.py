"""Cost, run times and saved manual work for the statistics page (/review/statistik).

Every recognition and every price search appends an entry to the sidecar (`laeufe`): model, tokens,
searches and seconds, plus the n8n execution id when the call came from workflow 01. Costs are computed
here from `statistik` in pricing.yaml, so a changed price list applies to old entries as well.
Minutes saved are an estimate from the assumed manual effort per step (pricing.yaml), not a measurement.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .storage import AKTIV, EINGANG, PAPIERKORB, VERKAUFT, NotFound, Store


def _ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def part_cost(part: dict | None, conf: dict) -> float:
    """USD of one recognition/price-search part from its tokens and searches."""
    if not part:
        return 0.0
    pin, pout = (conf.get("modellpreise_usd") or {}).get(part.get("modell"), (0.0, 0.0))
    return (part.get("input_tokens", 0) / 1e6 * pin + part.get("output_tokens", 0) / 1e6 * pout
            + part.get("suchen", 0) * float(conf.get("websuche_usd", 0)))


def entries_of(side: dict) -> list[dict]:
    """The sidecar's run entries; older sidecars only have ki_info (recognition tokens, no times)."""
    if side.get("laeufe"):
        return side["laeufe"]
    info = side.get("ki_info")
    if not info:
        return []
    return [{"alt": True, "zeit": side.get("erkannt_am"), "start": None, "art": "erkennung", "n8n": "", "gesamt_s": None,
             "erkennung": {"modell": info.get("model"), "input_tokens": info.get("input_tokens", 0),
                           "output_tokens": info.get("output_tokens", 0), "sekunden": None},
             "preissuche": None}]


def collect(store: Store, cfg: dict) -> dict:
    conf = cfg.get("statistik") or {}
    minutes = conf.get("gespart_minuten_je_lauf") or {}
    compare = conf.get("preissuche_vergleich") or {}
    runs: dict[str, dict] = {}
    models: dict[str, dict] = {}
    n = {"comics": 0, "alt": 0, "erkennungen": 0, "nutzbar": 0, "preissuchen": 0, "shopify": 0, "verkauft": 0}
    measured = {"comics": set(), "kosten": 0.0}
    cost_total = 0.0
    for prefix in (EINGANG, AKTIV, VERKAUFT, PAPIERKORB):
        for obj in store.list_scans(prefix):
            try:
                side = store.read_json(store.sidecar_key(prefix, obj.copy_id))
            except NotFound:
                continue
            entries = entries_of(side)
            if not entries:
                continue
            useful = prefix != PAPIERKORB  # deleted copies cost money but saved no work
            n["comics"] += 1
            n["alt"] += not side.get("laeufe")
            n["shopify"] += bool(useful and side.get("shopify"))
            n["verkauft"] += prefix == VERKAUFT
            for e in entries:
                end = _ts(e.get("zeit"))
                key = "alt" if e.get("alt") else e.get("n8n") or f"manuell-{obj.copy_id}-{e.get('zeit')}"
                run = runs.setdefault(key, {"id": e.get("n8n") or "", "alt": bool(e.get("alt")),
                                            "manuell": not e.get("n8n") and not e.get("alt"), "start": None,
                                            "ende": None, "comics": set(), "nutzbar": 0, "kosten": 0.0,
                                            "claude_s": 0.0, "gemessen": True})
                run["comics"].add(obj.copy_id)
                start = _ts(e.get("start")) or end
                if start and (run["start"] is None or start < run["start"]):
                    run["start"] = start
                if end and (run["ende"] is None or end > run["ende"]):
                    run["ende"] = end
                for part_name in ("erkennung", "preissuche"):
                    part = e.get(part_name)
                    if not part:
                        continue
                    c = part_cost(part, conf)
                    run["kosten"] += c
                    cost_total += c
                    if not e.get("alt"):
                        measured["comics"].add(obj.copy_id)
                        measured["kosten"] += c
                    m = models.setdefault(part.get("modell") or "?", {"aufrufe": 0, "kosten": 0.0, "sekunden": 0.0,
                                                                       "gemessen": 0})
                    m["aufrufe"] += 1
                    m["kosten"] += c
                    if part.get("sekunden") is not None:
                        m["sekunden"] += part["sekunden"]
                        m["gemessen"] += 1
                        run["claude_s"] += part["sekunden"]
                    else:
                        run["gemessen"] = False
                    if part_name == "erkennung":
                        n["erkennungen"] += 1
                        if useful:
                            n["nutzbar"] += 1
                            run["nutzbar"] += 1
                    else:
                        n["preissuchen"] += 1
    run_list = []
    for r in runs.values():
        dauer = (r["ende"] - r["start"]).total_seconds() if r["start"] and r["ende"] else None
        run_list.append({**r, "anzahl": len(r["comics"]), "dauer_s": dauer,
                         "gespart_min": r["nutzbar"] * float(minutes.get("erkennung", 0))})
    run_list.sort(key=lambda r: r["ende"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    workflows = [
        {"name": "01 Erkennung und Preisvorschlag", "anzahl": n["nutzbar"], "je_lauf": float(minutes.get("erkennung", 0))},
        {"name": "02 Nach Shopify", "anzahl": n["shopify"], "je_lauf": float(minutes.get("shopify", 0))},
        {"name": "03 Verkauf", "anzahl": n["verkauft"], "je_lauf": float(minutes.get("verkauf", 0))},
    ]
    for w in workflows:
        w["gespart"] = w["anzahl"] * w["je_lauf"]
    hypo = {name: n["preissuchen"] * v["usd"] for name, v in compare.items()}
    return {"gemessene_comics": len(measured["comics"]), "gemessene_kosten": measured["kosten"], "laeufe": run_list,
            "modelle": models, "zaehler": n, "kosten": cost_total, "workflows": workflows,
            "gespart_min": sum(w["gespart"] for w in workflows), "vergleich": compare, "klammer": hypo}
