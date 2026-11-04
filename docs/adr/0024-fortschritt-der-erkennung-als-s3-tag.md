# ADR-0024: Fortschritt von Workflow 01 als S3-Tag, die Review fragt ihn ab

- **Status:** Akzeptiert (PoC)
- **Datum:** 2026-11-04

## Kontext
Nach einem Foto-Upload startet Workflow 01 sofort (ADR-0018). Die Übersicht zeigte bis zum manuellen Neuladen nur
„Neu“ bzw. „Wird erkannt“. Man sah weder, ob der Workflow läuft und in welchem Schritt er ist, noch, wann das Comic
fertig ist. Der Zustand liegt nur in S3 (ADR-0004, ADR-0006).

## Entscheidung
- Während `recognize` trägt der Dienst den aktuellen Schritt als Tag am Scan in `eingang/` ein:
  `schritt=bilder|erkennung|preissuche` und `lauf=<n8n-Ausführungsnummer>` (Header `X-N8N-Lauf`, ADR-0023).
  Beim Übergang nach `offen` und `fehler` sowie beim „Erneut erkennen“ werden beide Tags entfernt.
- `GET /review/fortschritt?ids=…` liefert für bis zu 50 Scans Status, Schritt, Lauf und Startzeit (`claimed`).
- Die Übersicht zeigt auf Kacheln mit Status `neu`/`in-arbeit` die drei Schritte, die n8n-Laufnummer und die
  Laufzeit. Sie fragt alle 3 Sekunden ab (nicht, solange der Tab im Hintergrund ist) und lädt neu, sobald sich der
  Status einer Kachel ändert. Ist der Upload-Dialog offen, lädt sie erst nach dem Schließen neu.

## Konsequenzen
- Je Erkennung 3 zusätzliche Tag-Schreibvorgänge in S3 (je 2 Aufrufe), je Abfrage 1 Aufruf pro Kachel. Bei
  PoC-Mengen vernachlässigbar.
- Die Schritte spiegeln den Dienst, nicht die n8n-Knoten. Die Zeit vor dem Abholen durch n8n zeigt die Kachel
  als „Wartet auf Workflow 01“.

## Verworfene Alternativen
- n8n-REST-API abfragen: braucht einen weiteren Schlüssel und kennt die Schritte im Dienst nicht.
- WebSockets/Server-Sent Events: lange offene Verbindungen über den Port-Forward bzw. später den Tunnel, mehr Code für
  wenige Sekunden Gewinn.

## Bezug
ADR-0004, ADR-0006, ADR-0018, ADR-0023; `comic_helper/app.py` (`recognize`, `review_progress`), `templates/liste.html`.
