# ADR-0007: Scan-Upload per Sync-Skript mit UUID

- **Status:** Akzeptiert
- **Datum:** 2026-10-27

## Kontext
Plan 5: pro Comic eine zweiseitige PDF, Dateiname `{UUID}.pdf`, Ablage in `eingang/`. Ein FUSE-Mount im
Cluster wäre heikel (Offene Punkte 4).

## Entscheidung
- Scan-Software speichert beliebig benannte PDFs nach `/srv/scans/neu/`.
- `comics-scan-sync` (systemd-Timer, 1 min) prüft „nicht mehr in Bearbeitung“ und genau 2 Seiten,
  vergibt die UUID, lädt mit `If-None-Match` und Tag `status=neu` hoch, verschiebt lokal nach `hochgeladen/`.
- Falsche Seitenzahl → `fehler/`, kein Upload.
- Die UUID ist die Exemplar-ID für den ganzen Lebenszyklus.
- n8n holt neue Scans per Polling (alle 2 min), nicht per S3-Event.

## Konsequenzen
- Upload-Schlüssel kann nur schreiben (ADR-0003).
- Bis zu ~3 Minuten Verzögerung zwischen Scan und Erkennung.

## Verworfene Alternativen
- s3fs-Mount; S3-Event-Benachrichtigung an Webhook (mehr bewegliche Teile).

## Bezug
Plan 5; Rolle `sync`, Workflow 01
