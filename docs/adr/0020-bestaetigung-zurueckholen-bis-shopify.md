# ADR-0020: Bestätigung lässt sich bis zum Anlegen in Shopify zurückholen

- **Status:** Akzeptiert
- **Datum:** 2026-11-03
- **Ergänzt:** ADR-0006 (Review-Oberfläche), ADR-0014 (erst Shopify, dann S3-Metadaten)

## Kontext
Nach „Bestätigen und in den Shop“ steht ein Exemplar auf `status=bestaetigt` und war in der
Review-Oberfläche nicht mehr zu öffnen. Ein Tippfehler im Titel oder ein falscher Preis ließ sich
nicht mehr korrigieren, obwohl das Exemplar noch gar nicht in Shopify war (im PoC laufen die
Shopify-Workflows nicht, das Exemplar bleibt also beliebig lange bestätigt).

## Entscheidung
- Bestätigte Exemplare sind in der Liste wieder anklickbar. Die Detailansicht zeigt die Entscheidung
  schreibgeschützt und den Knopf „Zurückholen und ändern“.
- `POST /review/{id}/zurueckholen` setzt den Tag von `bestaetigt` zurück auf `offen`. Die
  Entscheidung im Sidecar bleibt und füllt das Formular vor; erneutes Bestätigen überschreibt sie.
- Nicht erlaubt, sobald der Sidecar einen `shopify`-Eintrag hat (Produkt/Variante angelegt). Dann
  wird in Shopify korrigiert, nicht im Review.

## Konsequenzen
- Korrekturen ohne Umweg über S3 oder Shopify, solange nichts veröffentlicht ist.
- Restrisiko bei laufendem Workflow 02: holt jemand zurück, während n8n gerade das Produkt anlegt,
  hat das Exemplar danach `status=offen` mit `shopify`-Eintrag. `finalize` verweigert dann (nicht
  bestätigt), und beim erneuten Bestätigen wird das bestehende Produkt nicht aktualisiert. Das
  Zeitfenster ist kurz; bei Bedarf später per Sperre im Sidecar schließen.

## Verworfene Alternativen
- Bestätigte Exemplare direkt bearbeitbar lassen – n8n könnte mitten in der Bearbeitung mit dem
  alten Stand nach Shopify schreiben.
- Zurückholen auch nach Shopify (Produkt löschen) – greift in den Shop ein, gehört nicht ins Review.

## Bezug
`comic_helper/app.py` (`POST /review/{id}/zurueckholen`), `templates/review.html`,
`templates/liste.html`, ADR-0006, ADR-0014.
