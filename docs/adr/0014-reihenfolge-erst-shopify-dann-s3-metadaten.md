# ADR-0014: Reihenfolge: erst Shopify, dann S3-Metadaten

- **Status:** Akzeptiert
- **Datum:** 2026-10-27

## Kontext
S3-Metadaten sollen einmalig geschrieben werden und die Shopify-Variant-ID enthalten (Plan 8, Reihenfolge-Empfehlung).

## Entscheidung
- Nach der Bestätigung: 1. Shopify-Variante anlegen (Ergebnis im Sidecar), 2. `finalize` schreibt alle
  Metadaten per CopyObject REPLACE und verschiebt nach `aktiv/`.
- `finalize` verweigert, solange keine Shopify-IDs vorliegen.
- Fehler bleiben im Status `bestaetigt` und werden vom 15-Minuten-Lauf wiederholt.

## Konsequenzen
- Ein Exemplar kann kurz in Shopify existieren, während die PDF noch in `eingang/` liegt (unkritisch).

## Verworfene Alternativen
- Metadaten zuerst und Variant-ID per zweitem Copy nachtragen (doppelte Schreibvorgänge).

## Bezug
Plan 8, 9; Workflow 02, `app.finalize`
