# ADR-0012: Shopify-Anbindung: Variante je Exemplar, Sammelposten, Dev-Dashboard-App

- **Status:** Akzeptiert; offen: Zustand als Produktoption oder als eigenes Produkt (E4 in `docs/GO-LIVE.md`)
- **Datum:** 2026-10-27, konsolidiert 2026-11-13 (enthält frühere ADR-0013, ADR-0021, ADR-0026)

## Kontext
Shopify ist Quelle der Wahrheit für den Bestand; jedes physische Exemplar wird einzeln verkauft. Viele Hefte liegen
aber 20- oder 100-mal vor, jedes einzeln zu scannen kostet zu viel Zeit. Shopify erlaubt seit 1.1.2026 keine neuen
benutzerdefinierten Apps im Shop-Admin mehr; neue Apps entstehen im Dev Dashboard und haben keinen festen Token.

## Entscheidung
- **Modell:** Ein Produkt je Titel + Ausgabe + Verlag (Handle aus diesen Teilen). Optionen `Zustand` und `Exemplar`
  (a, b, c …); jede Variante Menge 1 und eigene SKU. Anlegen idempotent: erst SKU-Suche, dann Handle, sonst neu.
  Verkaufte Varianten bleiben mit Bestand 0 stehen. Bilder sind die eigenen Scans.
- **SKU** = `<titel>-<ausgabe>-z<zustand>-<12 Hex-Stellen der UUID>` (z. B. `asterix-12-z3-7f3a9c2b1234`). Die Kurz-ID
  erlaubt, die PDF per S3-Präfix zu finden, statt 40.000 Objekte per HEAD zu durchsuchen, und Shopify-Exporte mit
  S3-Metadaten zu verbinden.
- **Sammelposten:** Anzahl > 1, fotografiert wird ein Beispielheft. Gewählt wird ein lückenloser Zustandsbereich
  (1 und 3 → 1–3). Ein Preis je Heft aus dem **Mittelwert** der Zustandsfaktoren (`sammelposten.preisregel`,
  überschreibbar). In Shopify eine Variante mit Bestand = Anzahl und Optionswert „Sammelposten · Zustand 1–3“;
  die Produktbeschreibung erklärt das einmal („nie schlechter als …, Bilder zeigen ein Beispielexemplar“).
  SKU mit Bereich: `asterix-12-z1-3-…`. S3: ein Scan, ein Objekt in `aktiv/`, Metadatum `anzahl`.
- **Anbindung:** App `comic-helper` im Dev Dashboard (`write_products`, `write_inventory`, `read_orders`,
  `read_locations`, `read_publications`). Der Dienst holt sich den 24-Stunden-Token selbst per `client_credentials`
  (Client-ID und -Schlüssel, nur in `comics.env`, ADR-0003), cacht ihn und holt ihn bei 401 neu.
  `SHOPIFY_ADMIN_TOKEN` bleibt für eine ältere App möglich.
- **Freigabe:** Produkte werden in der ersten Woche nach dem Go-Live als Entwurf angelegt (`shopify.produkt_status:
  DRAFT`) und von Hand freigeschaltet, danach `ACTIVE` (Änderung zuerst in der Sandbox, ADR-0027).

## Konsequenzen
- Shopify-Limit von 2.048 Varianten und 3 Optionen je Produkt reicht. Eine Umstellung von Option auf Produkt je
  Zustand betrifft nur `comic_helper/shopify.py`.
- Client-Credentials funktionieren nur, wenn App und Shop zur selben Shopify-Organisation gehören (hier erfüllt).
  `read_orders` gibt der App Zugriff auf Kundendaten; ohne Verkaufs-Workflow könnte der Bereich entfallen (ADR-0025).
- Bei Sammelposten passen Bild und Heft nicht eins zu eins zusammen. Der Mittelwert-Preis macht ein Z3-Heft aus dem
  Posten teurer als einzeln, ein Z1-Heft billiger. Weitere Hefte desselben Titels ergeben einen neuen Posten; ein
  bestehender Bestand wird nicht automatisch erhöht. Tagesmail und Statistik zählen Scans, nicht Hefte.
- SKUs sind länger als im ursprünglichen Plan; Kollisionswahrscheinlichkeit bei 40.000 Exemplaren < 1:100.000.

## Verworfene Alternativen
- Ein Produkt je Zustand; Mengen statt Einzelvarianten (Bild ↔ Exemplar nicht mehr zuordenbar).
- Je Zustand eine Variante mit eigener Menge im Sammelposten (jedes Heft müsste begutachtet werden); Preis nach dem
  schlechtesten Zustand (kundenfreundlich, nicht gewählt).
- SKU mit Mapping-Tabelle (bräuchte Datenbank); Token von Hand kopieren (läuft nach 24 Stunden ab);
  Entwicklungsshop über ein Partner-Konto (für den PoC abgewählt).

## Bezug
`comic_helper/shopify.py`, `config.py`, `pricing.py`, `config/pricing.yaml`, `docs/SHOPIFY-EINRICHTUNG.md`,
`docs/SCANNEN-UND-BESTAETIGEN.md`
