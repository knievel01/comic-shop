# ADR-0018: Foto-Upload über die Review-Oberfläche als zweiter Eingang

- **Status:** Akzeptiert
- **Datum:** 2026-11-02
- **Ergänzt:** ADR-0007 (Scan-Upload per Sync-Skript bleibt der Hauptweg)

## Kontext
Im PoC gibt es keinen Scanner, und auch später soll ein einzelnes Exemplar ohne Scanner erfasst werden
können, z. B. mit Handyfotos von Cover und Rückseite. Bisher kam ein Scan nur über `comics-scan-sync`
nach `eingang/`.

## Entscheidung
- Seite `/review/hochladen` im comic-helper (gleicher Passwortschutz wie die Review-Oberfläche):
  zwei Bilder (Cover, Rückseite), auf dem Handy aus Kamera oder Galerie.
- Der comic-helper baut daraus dieselbe Form wie der Scanner: zweiseitige PDF (Seite 1 Cover,
  Seite 2 Rückseite), A4, Bilder eingepasst, neue UUID als Exemplar-ID.
- Ablage `eingang/{UUID}.pdf` mit Tag `status=neu` in einem Aufruf, `If-None-Match: *` wie beim
  Sync-Skript. Ab da läuft alles wie bei einem Scan (Workflow 01 per Polling).
- Erlaubt: JPEG, PNG, WebP, AVIF; höchstens 25 MB je Bild. EXIF-Drehung wird angewendet.
- Rendern der Bilder unter derselben Sperre wie das PDF-Rendern der Erkennung (Speicher).

## Konsequenzen
- Kein neuer Dienst und kein neuer Schlüssel: der comic-helper darf schon nach `eingang/` schreiben.
- Fotos sind schlechter als Scans (Perspektive, Licht); die Erkennung bleibt dieselbe, die Prüfung
  in der Review-Oberfläche fängt Fehler ab.
- HEIC (iPhone-Originalformat) wird nicht gelesen; Safari liefert beim Hochladen in der Regel JPEG.

## Verworfene Alternativen
- Direkter Browser-Upload nach S3 mit vorsignierter URL – zwei Bilder müssten trotzdem serverseitig zur
  PDF zusammengesetzt werden.
- Eigener Upload-Dienst – mehr bewegliche Teile ohne Nutzen.

## Bezug
`comic_helper/app.py`, `comic_helper/pdf.py`, `comic_helper/storage.py`, `templates/hochladen.html`,
ADR-0003, ADR-0004, ADR-0006, ADR-0007.
