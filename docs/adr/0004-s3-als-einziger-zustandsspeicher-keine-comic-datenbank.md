# ADR-0004: S3 als einziger Zustandsspeicher, keine Comic-Datenbank

- **Status:** Akzeptiert
- **Datum:** 2026-10-27

## Kontext
Plan 0: Alle Metadaten liegen am Bild in S3, es gibt keine eigene Comic-Datenbank. S3-Metadaten sind
nachträglich nur per `CopyObject` mit `MetadataDirective=REPLACE` änderbar und auf 2 KB begrenzt.
Offene Review-Fälle dürfen bei Neustarts nicht verloren gehen.

## Entscheidung
- Präfixe: `eingang/`, `aktiv/`, `verkauft/`, `bilder/`, `backup/`. Der Ort einer PDF ist ihr Lebenszyklus.
- Arbeitsstatus innerhalb von `eingang/` als **Objekt-Tag** `status` (`neu`, `in-arbeit`, `offen`,
  `fehler`, `bestaetigt`) und `ki` (`sicher`, `nachkontrolle`); Tags sind änderbar.
- Veränderlicher Arbeitsstand (KI-Rohantwort, Entscheidung, Shopify-IDs) als Sidecar `<id>.json`
  neben der PDF; wandert beim Verschieben mit.
- Finale **Metadaten werden genau einmal** geschrieben: beim Verschieben nach `aktiv/` (REPLACE),
  ASCII bzw. URL-kodiert, Limit wird geprüft.
- Versioning an, alte Versionen nach 30 Tagen weg.
- Die interne n8n-Postgres-DB enthält keine Comic-Daten.

## Konsequenzen
- Kein Datenbankbetrieb für Comics; Zählungen (Tagesmail) über Listings/Tags (bei ~40.000 Objekten ok).
- Abfragen über Metadaten sind teuer (HEAD je Objekt); Suche nach Exemplar über Schlüsselpräfix (ADR-0013).

## Verworfene Alternativen
- Eigene Datenbank (widerspricht dem Zielbild); Status nur in n8n-Wait-Ausführungen (unsichtbar, an n8n gebunden).

## Bezug
Plan 0, 7, 8; `services/comic-helper/comic_helper/storage.py`
