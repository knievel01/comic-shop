# ADR-0013: SKU enthält die Kurz-ID des Exemplars

- **Status:** Akzeptiert, in Teilen ersetzt durch ADR-0025 (kein Verkaufs-Webhook mehr)
- **Datum:** 2026-10-27

## Kontext
Der Verkaufs-Webhook liefert die SKU je Bestellposition. Daraus muss die PDF in S3 schnell gefunden werden,
ohne 40.000 Objekte per HEAD zu durchsuchen (ADR-0004).

## Entscheidung
- SKU = `<titel>-<ausgabe>-z<zustand>-<12 Hex-Stellen der UUID>`, z. B. `asterix-12-z3-7f3a9c2b1234`.
- Suche per S3-Präfix `aktiv/7f3a9c2b-1234…`; Mehrdeutigkeit wird als Fehler erkannt.
- Der Buchstabe a/b/c (Plan-Beispiel) bleibt als Shopify-Option „Exemplar“ sichtbar.

## Konsequenzen
- Kollisionswahrscheinlichkeit bei 40.000 Exemplaren < 1:100.000.
- SKUs sind länger als im Plan-Beispiel.

## Verworfene Alternativen
- SKU `…-z3-a` mit Mapping-Tabelle (bräuchte Datenbank) oder Volltextsuche über Metadaten.

## Bezug
Plan 9, 10; `shopify.make_sku`, `storage.find_by_short_id`
