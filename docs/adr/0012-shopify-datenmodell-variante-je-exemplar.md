# ADR-0012: Shopify-Datenmodell: Variante je Exemplar

- **Status:** Vorgeschlagen
- **Datum:** 2026-10-27

## Kontext
Plan 9, Variante B: Shopify ist Quelle der Wahrheit für den Bestand; jedes physische Exemplar wird einzeln
verkauft. Offen ist laut Architekturdokument, ob Zustand eine Produktoption oder ein eigenes Produkt ist.

## Entscheidung
- Ein Produkt je Titel + Ausgabe + Verlag (Handle aus diesen drei Teilen).
- Optionen `Zustand` („2 – gut“) und `Exemplar` (a, b, c, …); jede Variante Menge 1, eigene SKU (ADR-0013).
- Anlegen idempotent: erst SKU-Suche, dann Produkt per Handle, sonst neues Produkt.
- Bilder: eigene Scans aus `bilder/`, Variante mit eigenem Cover verknüpft.
- Verkaufte Varianten bleiben mit Bestand 0 stehen (Theme blendet sie aus).

## Konsequenzen
- Shopify-Limit 2.048 Varianten / 3 Optionen pro Produkt reicht.
- Wird `Akzeptiert`, sobald Sepp die Frage „Option vs. Produkt je Zustand“ beantwortet hat; eine Umstellung
  betrifft nur `comic_helper/shopify.py`.

## Verworfene Alternativen
- Ein Produkt je Zustand; Mengen statt Einzelvarianten (Bild ↔ Exemplar nicht mehr zuordenbar).

## Bezug
Plan 9, Offene Punkte 2 und 6; `comic_helper/shopify.py`
