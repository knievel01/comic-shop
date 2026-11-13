# ADR-0007: Erfassung als 2-seitige PDF, Upload per Sync-Skript mit UUID

- **Status:** Akzeptiert
- **Datum:** 2026-10-27, konsolidiert 2026-11-13 (enthält frühere ADR-0018, ADR-0030)

## Kontext
Pro Comic entsteht eine zweiseitige PDF (Cover, Rückseite) mit der UUID als Dateiname in `eingang/`. Ein
FUSE-Mount im Cluster wäre heikel. Der geplante A3-Scanner ist noch nicht da; stattdessen gibt es eine Canon-Kamera.
Einzelne Exemplare sollen auch ohne Station erfassbar sein.

## Entscheidung
- Die Erfassung legt PDFs nach `/srv/scans/neu/`. `comics-scan-sync` (systemd-Timer, 1 min) prüft „nicht mehr in
  Bearbeitung“ und genau 2 Seiten, vergibt die UUID, lädt mit `If-None-Match` und Tag `status=neu` hoch und
  verschiebt lokal nach `hochgeladen/`. Falsche Seitenzahl → `fehler/`. **Die UUID ist die Exemplar-ID** für den
  ganzen Lebenszyklus. n8n holt neue Scans per Polling (2 min), nicht per S3-Event.
- **Standard-Eingang ist die Kamera** (Rolle `camera`, Skript `comics-capture`): Enter löst die Canon per gphoto2/USB aus,
  erst Cover, dann Rückseite; Ergebnis ist dieselbe 2-seitige PDF. Ein SANE-Scanner bleibt möglich.
- **Zweiter Eingang: Foto-Upload** im Review (`/review/hochladen`, z. B. Handyfotos). Der comic-helper baut dieselbe
  2-seitige PDF und legt sie wie der Sync-Weg in `eingang/` ab. Der comic-helper darf schon dorthin schreiben:
  kein neuer Dienst, kein neuer Schlüssel.

## Konsequenzen
- Der Upload-Schlüssel kann nur schreiben (ADR-0003). Bis zu ~3 Minuten zwischen Aufnahme und Erkennung.
- Die Kamera muss von libgphoto2 mit Fernauslösung unterstützt werden (vorher `comics-capture --probe`).
- Fotos sind schlechter als Scans (Perspektive, Licht); die Prüfung im Review fängt Fehler ab. HEIC wird nicht gelesen.
- Zwei Auslösungen je Comic; Zeit je Comic ist zu messen. Ausbau: `future-improvements/001`.

## Verworfene Alternativen
- s3fs-Mount; S3-Event an Webhook (mehr bewegliche Teile).
- Direkter Browser-Upload mit vorsignierter URL oder eigener Upload-Dienst (PDF muss trotzdem serverseitig entstehen).
- Handy-Upload als Standard (mehr Handarbeit); Kamera per HDMI/Webcam-Modus (schlechtere Qualität).

## Bezug
Rollen `sync`, `camera`; Workflow 01; `comic_helper/pdf.py`, `app.py`
