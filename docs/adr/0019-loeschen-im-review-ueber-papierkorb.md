# ADR-0019: Löschen im Review verschiebt das Exemplar in den Papierkorb

- **Status:** Akzeptiert
- **Datum:** 2026-11-03
- **Ergänzt:** ADR-0004 (S3 als einziger Zustandsspeicher), ADR-0006 (Review-Oberfläche)

## Kontext
Im Eingang landen auch Scans und Fotos, die nie in den Shop sollen: Fehlaufnahmen, doppelte
Uploads, Testbilder, Exemplare, die doch nicht verkauft werden. Bisher konnte man sie in der
Review-Oberfläche nur liegen lassen; „Zu prüfen“ füllt sich dann mit Altlasten.

## Entscheidung
- In der Detailansicht gibt es neben „Bestätigen und in den Shop“ den Knopf „Löschen“, mit
  Rückfrage im Browser.
- Löschen ist nur für die Zustände `offen` und `fehler` erlaubt (die prüfbaren). Ein `neu`/
  `in-arbeit`-Exemplar gehört gerade n8n, ein `bestaetigt`-Exemplar ist auf dem Weg nach Shopify.
- „Löschen“ verschiebt `eingang/<id>.pdf` samt Sidecar nach `papierkorb/<id>.pdf`, Tag
  `status=geloescht` und `geloescht=<Unix-Zeit>`. Die Bilder unter `bilder/` bleiben liegen.
- Nichts wird endgültig gelöscht. Wiederherstellen: PDF und Sidecar per Hand zurück nach
  `eingang/` kopieren und den Tag auf `status=offen` setzen.

## Konsequenzen
- Ein Fehlklick ist reparierbar; kein neuer Schlüssel und keine neue IAM-Regel (der comic-helper
  darf schon im ganzen Bucket schreiben).
- `papierkorb/` wächst. Eine Lifecycle-Regel (z. B. endgültig löschen nach 90 Tagen, samt
  zugehöriger `bilder/`) ist ein späterer Schritt, sobald der Bucket per Terraform verwaltet wird.
- Neuer Ort in der Zustandstabelle von `docs/ARCHITEKTUR.md`.

## Verworfene Alternativen
- Sofort endgültig löschen – ein Fehlklick wäre nicht rückgängig zu machen.
- Nur einen Tag `status=geloescht` in `eingang/` setzen – jede Liste und jeder Workflow müsste
  ihn ausfiltern; ein eigener Präfix hält den Eingang sauber.

## Bezug
`comic_helper/app.py` (`POST /review/{id}/loeschen`), `comic_helper/storage.py`,
`templates/review.html`, `templates/liste.html`, `docs/ARCHITEKTUR.md`, ADR-0004, ADR-0006.
