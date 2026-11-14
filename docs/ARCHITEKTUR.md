# Architektur

## Überblick

```
 Scanner ──NAPS2──> /srv/scans/neu/*.pdf
                         │  comics-scan-sync (systemd-Timer, 1 min)
                         │  prüft 2 Seiten, vergibt UUID, nur PutObject-Recht
                         ▼
 S3  eingang/<id>.pdf  (Tag status=neu)  <── oder Foto-Upload /review/hochladen (ADR-0007)
                         │
 n8n 01 Scan-Ingest (alle 2 min) ──> comic-helper
                         │  claim -> PDF->JPEG -> Claude -> Vorschlag + Preisvorschlag
                         │  -> Inhaltstext (Schritt „inhalt“, wenn inhalt.aktiv, ADR-0010)
                         ▼
 S3  eingang/<id>.json, bilder/<id>-1|2.jpg, Tag status=offen, ki=sicher|nachkontrolle
                         │
 Fachkraft: https://comics-01/review/  (comic-helper, nur LAN)
                         │  Titel/Zustand/Z1-Preis/Inhaltstext bestätigen, Endpreis live
                         ▼
 Tag status=bestaetigt ──Webhook──> n8n 02 (+ 15-min-Nachzügler)
                         │  1. Shopify: Produkt/Variante anlegen (idempotent per SKU),
                         │     Inhaltstext ins Metafeld comic.inhalt (nur wenn leer, ADR-0012)
                         │  2. S3: Metadaten per CopyObject REPLACE, nach aktiv/
                         ▼
 S3  aktiv/<id>.pdf (alle Metadaten am Objekt)          Shopify: Variante, Menge 1
                                                            │
                                     Verkauf, Storno, Retoure nur in Shopify,
                                     kein Rückkanal zum Rechner (ADR-0025)

 n8n 04 täglich 7:00 ──> comic-helper /api/report/daily ──> Mail
 n8n 99 Fehler-Alarm  <── errorWorkflow aller Workflows
```

Alles läuft auf einem Rechner (Ubuntu 24.04, K3s), Namespace `comics`:
`postgres` (nur n8n-intern), `n8n`, `comic-helper`. Aus dem Internet ist nichts erreichbar (ADR-0025).

## Zustände eines Exemplars

| Ort | Tag `status` | Bedeutung |
| --- | --- | --- |
| `eingang/` | `neu` | hochgeladen, noch nicht verarbeitet |
| `eingang/` | `in-arbeit` | von n8n übernommen (nach 30 min ohne Ergebnis wieder frei); Tag `schritt` (bilder, erkennung, preissuche, inhalt) und `lauf` (n8n-Nummer) zeigen den Fortschritt (ADR-0004) |
| `eingang/` | `offen` | KI-Vorschlag liegt vor, wartet auf Fachkraft |
| `eingang/` | `fehler` | Erkennung fehlgeschlagen, im Review sichtbar („Erneut erkennen“) |
| `eingang/` | `bestaetigt` | Fachkraft hat bestätigt, Shopify/Metadaten stehen aus; bis Shopify zurückholbar (ADR-0006) |
| `aktiv/` | `aktiv` | in Shopify angelegt, Metadaten final; bleibt auch nach dem Verkauf hier (ADR-0025) |
| `papierkorb/` | `geloescht` | im Review gelöscht, wiederherstellbar (ADR-0004) |

Der Arbeitsstand (KI-Rohantwort, Entscheidung, Shopify-IDs) steht in `<prefix>/<id>.json`
neben der PDF. Er wird beim Verschieben mitgenommen.

## Entscheidungen

Alle Architektur- und Fachentscheidungen stehen als ADRs in [`docs/adr/`](adr/README.md) und sind verbindlich.
Kurzüberblick:

| Thema | ADR |
| --- | --- |
| Ein Laptop, reproduzierbare Installation, Geheimnisse | [0001](adr/0001-ein-laptop-fuer-scan-station-und-server.md), [0002](adr/0002-autoinstall-iso-und-ansible-pull.md), [0003](adr/0003-geheimnisse-nie-in-repo-oder-image.md) |
| S3 als einziger Zustandsspeicher | [0004](adr/0004-s3-als-einziger-zustandsspeicher-keine-comic-datenbank.md) |
| comic-helper vs. n8n, Review-Oberfläche, n8n-Betrieb | [0005](adr/0005-fachlogik-im-dienst-comic-helper-n8n-orchestriert.md), [0006](adr/0006-review-oberflaeche-im-comic-helper-statt-n8n-formular.md), [0008](adr/0008-n8n-als-einzelinstanz-mit-postgres-auf-k3s.md) |
| Erfassung (Kamera, Scanner, Foto-Upload) | [0007](adr/0007-erfassung-als-pdf-upload-per-sync-skript.md) |
| Erkennung und Preise | [0010](adr/0010-erkennung-mit-claude-ximilar-nur-nach-vergleichstest.md), [0011](adr/0011-preisfindung-comicguide-skala-booklooker-ohne-scraping.md) |
| Shopify, SKU, Sammelposten | [0012](adr/0012-shopify-anbindung-variante-je-exemplar.md) |
| Zugriff nur im LAN, kein Rückkanal | [0025](adr/0025-kein-internetzugang-zugriff-nur-im-lan.md) |
| Sandbox, Rollout, getrennte Daten | [0027](adr/0027-sandbox-zuerst-rollout-per-ssh.md) |
