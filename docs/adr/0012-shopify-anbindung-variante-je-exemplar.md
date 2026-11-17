# ADR-0012: Shopify-Anbindung: Variante je Zustand, Batch-Erfassung, Dev-Dashboard-App

- **Status:** Akzeptiert (Modell geändert am 2026-11-17, Umsetzung offen: #11, #12, #13)
- **Datum:** 2026-10-27, konsolidiert 2026-11-13 (enthält frühere ADR-0013, ADR-0021, ADR-0026), Modell 2026-11-17

## Kontext
- Shopify ist Quelle der Wahrheit für den Bestand, über alle Kanäle (eigener Shop, eBay).
- Comics werden über eBay als Variantenangebote verkauft.
- Heute liegen ca. 1.000 Comics als Variantenartikel auf eBay, noch nicht in Shopify (Übernahme: #15).
- Viele Hefte liegen 20- oder 100-mal vor. Jedes einzeln scannen kostet zu viel Zeit.
- Shopify erlaubt seit 1.1.2026 keine neuen benutzerdefinierten Apps im Shop-Admin. Neue Apps entstehen im
  Dev Dashboard und haben keinen festen Token.

## Entscheidung
- **Modell:** ein Produkt je Titel + Ausgabe + Verlag (Handle aus diesen Teilen). Eine Option `Zustand`.
  Eine Variante je Zustandswert, Menge = Anzahl Hefte.
- **Zustandswert:** gibt der Workflow vor, entweder eine Stufe (`1`) oder ein Bereich (`1–2`, `1–3` …).
- **Nachbuchen:** Neue Hefte mit gleichem Zustandswert erhöhen den Bestand der vorhandenen Variante.
  Anlegen idempotent: erst SKU-Suche, dann Handle, sonst neu.
- **SKU:** `<titel>-<ausgabe>-z<zustand>`, bei einem Bereich `z1-2` (z. B. `asterix-12-z3`, `asterix-12-z1-2`). Ohne UUID.
- **Batch-Erfassung:** ein Beispielscan, Stückzahl je Zustandswert. Jeder Zustandswert bucht auf seine Variante.
  S3: ein Scan, ein Objekt in `aktiv/`, Metadaten mit Stückzahl je Zustandswert.
- **Preis Bereich:** Mittelwert der Zustandsfaktoren (`sammelposten.preisregel`, überschreibbar).
- **Bilder:** die eigenen Scans.
- **Anbindung:** App `comic-helper` im Dev Dashboard (`write_products`, `write_inventory`, `read_orders`,
  `read_locations`, `read_publications`). Token per `client_credentials` (Client-ID und -Schlüssel nur in
  `comics.env`, ADR-0003), 24 Stunden gültig, gecacht, bei 401 neu geholt. `SHOPIFY_ADMIN_TOKEN` bleibt für eine
  ältere App möglich.
- **Inhaltstext:** Metafeld `comic.inhalt` (mehrzeiliger Text, Storefront-Zugriff „lesen“). Nur gesetzt, wenn leer.
  Beschreibung bleibt unberührt (eBay liest sie). Ein Fehler beim Metafeld bricht das Anlegen nicht ab.
- **Freigabe:** `shopify.produkt_status: ACTIVE` seit 12.11.2026 (Änderung zuerst in der Sandbox, ADR-0027).

## Konsequenzen
- Passt zu eBay-Variantenangeboten.
- Bild ↔ Exemplar nicht mehr eindeutig. Die Bilder zeigen ein Beispielheft.
- SKU ↔ S3 ist n:1: mehrere Scans buchen auf eine Variante. Ein Exemplar wird über die UUID im S3-Schlüssel gefunden (ADR-0007).
- Mehrere Hefte je Variante: Doppelverkauf möglich, wenn die eBay-Synchronisierung verzögert ist.
- Mittelwertpreis: ein Z3-Heft im Bereich ist teurer als einzeln, ein Z1-Heft billiger.
- Shopify-Limit (2.048 Varianten, 3 Optionen je Produkt) wird nicht erreicht.
- Client-Credentials gehen nur, wenn App und Shop zur selben Shopify-Organisation gehören (erfüllt).
- `read_orders` gibt Zugriff auf Kundendaten. Ohne Verkaufs-Workflow könnte der Bereich entfallen (ADR-0025).
- Offen: Preis, wenn ein neuer Scan einen anderen Preis ergibt als die vorhandene Variante. Variantenbild.

## Verworfene Alternativen
- Variante je Exemplar mit Menge 1 und UUID-Kurz-ID in der SKU (Modell bis 2026-11-17): passt nicht zu
  eBay-Variantenangeboten, Batch-Erfassung zu aufwendig.
- Ein Produkt je Zustand.
- Preis nach dem schlechtesten Zustand im Bereich.
- SKU mit Mapping-Tabelle (bräuchte Datenbank). Token von Hand kopieren (läuft nach 24 Stunden ab).
  Entwicklungsshop über ein Partner-Konto.

## Bezug
`comic_helper/shopify.py`, `config.py`, `pricing.py`, `config/pricing.yaml`, `docs/SHOPIFY-EINRICHTUNG.md`,
`docs/SCANNEN-UND-BESTAETIGEN.md`, Issues #11, #12, #13
