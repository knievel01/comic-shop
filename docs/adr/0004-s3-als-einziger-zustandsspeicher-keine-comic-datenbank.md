# ADR-0004: S3 als einziger Zustandsspeicher, keine Comic-Datenbank

- **Status:** Akzeptiert
- **Datum:** 2026-10-27, konsolidiert 2026-11-13 (enthält frühere ADR-0014, ADR-0019, ADR-0024)

## Kontext
Alle Metadaten liegen am Bild in S3, es gibt keine eigene Comic-Datenbank. S3-Metadaten sind nachträglich nur
per `CopyObject` mit `MetadataDirective=REPLACE` änderbar und auf 2 KB begrenzt. Offene Review-Fälle dürfen
bei Neustarts nicht verloren gehen.

## Entscheidung
- Präfixe: `eingang/`, `aktiv/`, `bilder/`, `papierkorb/`, `backup/`. Der Ort einer PDF ist ihr Lebenszyklus.
  `aktiv/` enthält auch bereits verkaufte Exemplare (ADR-0025).
- Arbeitsstatus in `eingang/` als **Objekt-Tag** `status` (`neu`, `in-arbeit`, `offen`, `fehler`, `bestaetigt`)
  und `ki` (`sicher`, `nachkontrolle`). Während der Erkennung zeigen die Tags `schritt` und `lauf` (n8n-Nummer) den
  Fortschritt; die Review-Oberfläche fragt sie ab.
- Veränderlicher Arbeitsstand (KI-Rohantwort, Entscheidung, Shopify-IDs, Läufe mit Token und Dauer) als Sidecar
  `<id>.json` neben der PDF; wandert beim Verschieben mit.
- Finale **Metadaten werden genau einmal** geschrieben: beim Verschieben nach `aktiv/` (REPLACE). Davor legt
  n8n die Shopify-Variante an, `finalize` verweigert ohne Shopify-IDs. Fehler bleiben auf `bestaetigt` und
  werden vom 15-Minuten-Lauf wiederholt.
- **Löschen verschiebt nach `papierkorb/`** (Tag `status=geloescht`), nie endgültig; nur für `offen` und `fehler`.
- Versioning an, alte Versionen nach 30 Tagen weg. Die n8n-Postgres-DB enthält keine Comic-Daten.

## Konsequenzen
- Kein Datenbankbetrieb für Comics; Zählungen und Statistik über Listings, Tags und Sidecars (bei ~40.000
  Objekten ok, bei deutlich mehr wäre ein Zwischenspeicher nötig).
- Abfragen über Metadaten sind teuer (HEAD je Objekt); Suche nach Exemplar über Schlüsselpräfix (ADR-0012, SKU).
- Ein Exemplar kann kurz in Shopify existieren, während die PDF noch in `eingang/` liegt (unkritisch).
- Je Erkennung einige zusätzliche Tag-Schreibvorgänge; bei den Mengen vernachlässigbar.
- `papierkorb/` wächst; eine Lifecycle-Regel ist ein späterer Schritt.

## Verworfene Alternativen
- Eigene Datenbank (widerspricht dem Zielbild); Status nur in n8n-Wait-Ausführungen (unsichtbar, an n8n gebunden).
- Metadaten vor Shopify schreiben und die Variant-ID nachtragen (doppelte Schreibvorgänge).
- Fortschritt über die n8n-REST-API oder WebSockets (weiterer Schlüssel, kennt die Dienst-Schritte nicht).

## Bezug
`services/comic-helper/comic_helper/storage.py`, `docs/ARCHITEKTUR.md` (Zustandstabelle)
