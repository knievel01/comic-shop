# ADR-0016: Verkauf über Order-Webhooks, idempotent

- **Status:** Ersetzt durch ADR-0025
- **Datum:** 2026-10-27

## Kontext
Plan 10: Verkauf verschiebt das Bild nach `verkauft/`. `inventory_levels/update` liefert nur die
Inventory-Item-ID; Shopify stellt Webhooks mindestens einmal zu.

## Entscheidung
- Topics `orders/paid` (→ `verkauft/`), `orders/cancelled` und `refunds/create` mit Restock (→ zurück nach `aktiv/`).
- HMAC-Prüfung über den unveränderten Body; n8n reicht den Raw-Body an den comic-helper weiter.
- Idempotent über den Ort des Objekts: Doppelte Zustellung ändert nichts.
- Bei Fehlern antwortet n8n mit 500, damit Shopify erneut zustellt; der Fehler-Alarm meldet es.

## Konsequenzen
- Verkaufsvermerk (`verkauft-am`, `bestellung`) wird per REPLACE an die Metadaten angehängt.

## Verworfene Alternativen
- `inventory_levels/update` (zusätzlicher Lookup nötig).

## Bezug
Plan 10; `comic_helper/webhooks.py`, Workflow 03
