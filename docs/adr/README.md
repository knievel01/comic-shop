# Architecture Decision Records

**Verbindliche Grundlage für alle Arbeiten in diesem Repo** (siehe [ADR-0000](0000-adrs-als-grundlage.md) und `CLAUDE.md`).
Neue oder geänderte Entscheidungen: neues ADR aus [`_vorlage.md`](_vorlage.md), altes ADR auf `Ersetzt durch ADR-NNNN` setzen.

| Nr. | Titel | Status |
| --- | --- | --- |
| [0000](0000-adrs-als-grundlage.md) | ADRs als verbindliche Entscheidungsgrundlage | Akzeptiert |
| [0001](0001-ein-rechner-fuer-scan-station-und-server.md) | Ein Rechner für Scan-Station und Server | Akzeptiert (vorläufig) |
| [0002](0002-autoinstall-iso-und-ansible-pull.md) | Reproduzierbare Installation: Autoinstall-ISO und ansible-pull | Akzeptiert |
| [0003](0003-geheimnisse-nie-in-repo-oder-image.md) | Geheimnisse nie in Repo oder Image | Akzeptiert |
| [0004](0004-s3-als-einziger-zustandsspeicher-keine-comic-datenbank.md) | S3 als einziger Zustandsspeicher, keine Comic-Datenbank | Akzeptiert |
| [0005](0005-fachlogik-im-dienst-comic-helper-n8n-orchestriert.md) | Fachlogik im Dienst comic-helper, n8n orchestriert | Akzeptiert |
| [0006](0006-review-oberflaeche-im-comic-helper-statt-n8n-formular.md) | Review-Oberfläche im comic-helper statt n8n-Formular | Akzeptiert |
| [0007](0007-scan-upload-per-sync-skript-mit-uuid.md) | Scan-Upload per Sync-Skript mit UUID | Akzeptiert |
| [0008](0008-n8n-als-einzelinstanz-mit-postgres-auf-k3s.md) | n8n als Einzelinstanz mit Postgres auf K3s | Akzeptiert |
| [0009](0009-oeffentlich-nur-webhook-ueber-cloudflare-tunnel.md) | Öffentlich nur /webhook/* über Cloudflare-Tunnel | Akzeptiert |
| [0010](0010-erkennung-mit-claude-ximilar-nur-nach-vergleichstest.md) | Erkennung mit Claude, Ximilar nur nach Vergleichstest | Vorgeschlagen |
| [0011](0011-preisfindung-comicguide-skala-ohne-scraping.md) | Preisfindung nach Comicguide-Skala, zentral konfiguriert, kein Scraping | Akzeptiert |
| [0012](0012-shopify-datenmodell-variante-je-exemplar.md) | Shopify-Datenmodell: Variante je Exemplar | Vorgeschlagen |
| [0013](0013-sku-enthaelt-die-kurz-id-des-exemplars.md) | SKU enthält die Kurz-ID des Exemplars | Akzeptiert |
| [0014](0014-reihenfolge-erst-shopify-dann-s3-metadaten.md) | Reihenfolge: erst Shopify, dann S3-Metadaten | Akzeptiert |
| [0015](0015-iso-als-release-artefakt-in-teilen.md) | ISO als Release-Artefakt in Teilen | Akzeptiert |
| [0016](0016-verkauf-ueber-order-webhooks-idempotent.md) | Verkauf über Order-Webhooks, idempotent | Akzeptiert |
| [0017](0017-poc-booklooker-angebotspreis-als-standardquelle.md) | PoC: Booklooker-Angebotspreis als Standard-Preisquelle, mit Beleg | Akzeptiert (nur PoC), ergänzt 0011 |
| [0018](0018-foto-upload-ueber-die-review-oberflaeche.md) | Foto-Upload über die Review-Oberfläche als zweiter Eingang | Akzeptiert, ergänzt 0007 |
