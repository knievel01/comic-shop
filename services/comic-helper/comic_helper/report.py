"""Daily summary (7:00): scanned, open reviews, confident vs. needs re-check."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import storage
from .storage import AKTIV, EINGANG, VERKAUFT, Store

TZ = ZoneInfo("Europe/Berlin")


def daily(store: Store, now: datetime | None = None, hours: int = 24) -> dict:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)

    gescannt = sicher = nachkontrolle = 0
    offen_neu = 0
    totals = {"offen": 0, "sicher": 0, "nachkontrolle": 0, "fehler": 0, "bestaetigt": 0, "in-arbeit": 0, "neu": 0}

    for obj in store.list_scans(EINGANG):
        tags = store.get_tags(obj.key)
        status = tags.get("status", "neu")
        totals[status] = totals.get(status, 0) + 1
        if status == "offen":
            totals[tags.get("ki", "nachkontrolle")] = totals.get(tags.get("ki", "nachkontrolle"), 0) + 1
        if since <= obj.last_modified <= now:  # tagging does not change LastModified
            gescannt += 1
            if status in ("offen", "bestaetigt", "fehler", "neu", "in-arbeit"):
                offen_neu += 1
            if tags.get("ki") == "sicher":
                sicher += 1
            elif tags.get("ki") == "nachkontrolle" or status == "fehler":
                nachkontrolle += 1

    # Copies scanned in the window and already confirmed: moved to aktiv/verkauft (copy changes
    # LastModified, so only recently moved objects can qualify; the scan time is in metadata).
    lo, hi = since.strftime("%Y-%m-%dT%H:%M:%SZ"), now.strftime("%Y-%m-%dT%H:%M:%SZ")
    bestaetigt_heute = 0
    verkauft_heute = 0
    for prefix in (AKTIV, VERKAUFT):
        for obj in store.list_scans(prefix):
            if not since <= obj.last_modified:
                continue
            meta = storage.decode_metadata(store.head(obj.key).get("Metadata", {}))
            if prefix == VERKAUFT and lo <= meta.get("verkauft-am", "") <= hi:
                verkauft_heute += 1
            scanned_at = meta.get("gescannt-am", "")
            if scanned_at and lo <= scanned_at <= hi:
                gescannt += 1
                bestaetigt_heute += 1
                if meta.get("ki-status") == "sicher":
                    sicher += 1
                else:
                    nachkontrolle += 1

    result = {
        "zeitraum_von": since.astimezone(TZ).isoformat(timespec="minutes"),
        "zeitraum_bis": now.astimezone(TZ).isoformat(timespec="minutes"),
        "gescannt": gescannt,
        "offen": offen_neu,
        "sicher": sicher,
        "nachkontrolle": nachkontrolle,
        "bestaetigt_aus_zeitraum": bestaetigt_heute,
        "verkauft": verkauft_heute,
        "gesamt_offen": totals.get("offen", 0) + totals.get("neu", 0) + totals.get("in-arbeit", 0),
        "gesamt_offen_sicher": totals.get("sicher", 0),
        "gesamt_offen_nachkontrolle": totals.get("nachkontrolle", 0),
        "gesamt_fehler": totals.get("fehler", 0),
        "gesamt_bestaetigt_nicht_im_shop": totals.get("bestaetigt", 0),
    }
    result["text"] = format_text(result)
    return result


def format_text(r: dict) -> str:
    return (
        f"Comic-Tagesbericht ({r['zeitraum_von'][:16].replace('T', ' ')} bis {r['zeitraum_bis'][11:16]} Uhr)\n\n"
        f"Gescannt:            {r['gescannt']}\n"
        f"davon noch offen:    {r['offen']}\n"
        f"KI sicher:           {r['sicher']}\n"
        f"KI Nachkontrolle:    {r['nachkontrolle']}\n"
        f"Verkauft:            {r['verkauft']}\n\n"
        f"Insgesamt offen:     {r['gesamt_offen']} "
        f"({r['gesamt_offen_sicher']} sicher, {r['gesamt_offen_nachkontrolle']} Nachkontrolle)\n"
        f"Fehler (Nacharbeit): {r['gesamt_fehler']}\n"
        f"Bestätigt, noch nicht im Shop: {r['gesamt_bestaetigt_nicht_im_shop']}\n"
    )
