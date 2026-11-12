# Architecture Decision Records

**Verbindliche Grundlage für alle Arbeiten in diesem Repo** (siehe [ADR-0000](0000-adrs-als-grundlage.md) und `CLAUDE.md`).
Neue oder geänderte Entscheidungen: neues ADR aus [`_vorlage.md`](_vorlage.md), altes ADR auf `Ersetzt durch ADR-NNNN` setzen.

| Nr. | Titel | Status |
| --- | --- | --- |
| [0000](0000-adrs-als-grundlage.md) | ADRs als verbindliche Entscheidungsgrundlage | Akzeptiert |
| [0001](0001-ein-rechner-fuer-scan-station-und-server.md) | Ein Rechner für Scan-Station und Server | Akzeptiert (vorläufig) |
| [0002](0002-autoinstall-iso-und-ansible-pull.md) | Reproduzierbare Installation: Autoinstall-ISO und ansible-pull | Akzeptiert |
| [0003](0003-geheimnisse-nie-in-repo-oder-image.md) | Geheimnisse nie in Repo oder Image | Akzeptiert |
| [0004](0004-s3-als-einziger-zustandsspeicher-keine-comic-datenbank.md) | S3 als einziger Zustandsspeicher, keine Comic-Datenbank | Akzeptiert, in Teilen ersetzt durch 0025 |
| [0005](0005-fachlogik-im-dienst-comic-helper-n8n-orchestriert.md) | Fachlogik im Dienst comic-helper, n8n orchestriert | Akzeptiert |
| [0006](0006-review-oberflaeche-im-comic-helper-statt-n8n-formular.md) | Review-Oberfläche im comic-helper statt n8n-Formular | Akzeptiert |
| [0007](0007-scan-upload-per-sync-skript-mit-uuid.md) | Scan-Upload per Sync-Skript mit UUID | Akzeptiert |
| [0008](0008-n8n-als-einzelinstanz-mit-postgres-auf-k3s.md) | n8n als Einzelinstanz mit Postgres auf K3s | Akzeptiert |
| [0009](0009-oeffentlich-nur-webhook-ueber-cloudflare-tunnel.md) | Öffentlich nur /webhook/* über Cloudflare-Tunnel | Ersetzt durch 0025 |
| [0010](0010-erkennung-mit-claude-ximilar-nur-nach-vergleichstest.md) | Erkennung mit Claude, Ximilar nur nach Vergleichstest | Vorgeschlagen |
| [0011](0011-preisfindung-comicguide-skala-ohne-scraping.md) | Preisfindung nach Comicguide-Skala, zentral konfiguriert, kein Scraping | Akzeptiert, Preisquelle vorläufig durch 0028 ergänzt |
| [0012](0012-shopify-datenmodell-variante-je-exemplar.md) | Shopify-Datenmodell: Variante je Exemplar | Vorgeschlagen |
| [0013](0013-sku-enthaelt-die-kurz-id-des-exemplars.md) | SKU enthält die Kurz-ID des Exemplars | Akzeptiert, in Teilen ersetzt durch 0025 |
| [0014](0014-reihenfolge-erst-shopify-dann-s3-metadaten.md) | Reihenfolge: erst Shopify, dann S3-Metadaten | Akzeptiert |
| [0015](0015-iso-als-release-artefakt-in-teilen.md) | ISO als Release-Artefakt in Teilen | Akzeptiert |
| [0016](0016-verkauf-ueber-order-webhooks-idempotent.md) | Verkauf über Order-Webhooks, idempotent | Ersetzt durch 0025 |
| [0017](0017-poc-booklooker-angebotspreis-als-standardquelle.md) | PoC: Booklooker-Angebotspreis als Standard-Preisquelle, mit Beleg | Ersetzt durch 0028 |
| [0018](0018-foto-upload-ueber-die-review-oberflaeche.md) | Foto-Upload über die Review-Oberfläche als zweiter Eingang | Akzeptiert, ergänzt 0007 |
| [0019](0019-loeschen-im-review-ueber-papierkorb.md) | Löschen im Review verschiebt das Exemplar in den Papierkorb | Akzeptiert, ergänzt 0004/0006 |
| [0020](0020-bestaetigung-zurueckholen-bis-shopify.md) | Bestätigung lässt sich bis zum Anlegen in Shopify zurückholen | Akzeptiert, ergänzt 0006/0014 |
| [0021](0021-shopify-dev-dashboard-app-mit-client-credentials.md) | Shopify-Anbindung über eine Dev-Dashboard-App mit Client-Credentials | Akzeptiert, ergänzt 0012/0003, in Teilen ersetzt durch 0025 |
| [0022](0022-automatischer-preisvorschlag-per-websuche.md) | Automatischer Preisvorschlag aus Booklooker/ZVAB per Anthropic-Websuche | Akzeptiert (durch 0028 auch Zielbetrieb), ergänzt 0017/0011 |
| [0023](0023-statistik-seite-fuer-kosten-laufzeit-und-zeitersparnis.md) | Statistik-Seite für KI-Kosten, Laufzeiten und gesparte Handarbeit | Akzeptiert (durch 0028 auch Zielbetrieb), ergänzt 0004/0022, in Teilen ersetzt durch 0025 |
| [0024](0024-fortschritt-der-erkennung-als-s3-tag.md) | Fortschritt von Workflow 01 als S3-Tag, die Review fragt ihn ab | Akzeptiert (durch 0028 auch Zielbetrieb), ergänzt 0004/0018 |
| [0025](0025-kein-rueckkanal-von-shopify-verkauf-nur-in-shopify.md) | Kein Rückkanal von Shopify, Verkäufe werden nur in Shopify geführt | Akzeptiert, ersetzt 0009/0016 |
| [0026](0026-sammelposten-mehrere-gleiche-hefte-als-eine-variante.md) | Sammelposten: mehrere gleiche Hefte als eine Variante mit Zustandsbereich | Akzeptiert, ergänzt 0011/0012/0013/0018 |
| [0027](0027-poc-bleibt-als-sandbox-aenderungen-zuerst-dort.md) | Der PoC bleibt als Sandbox, Änderungen laufen zuerst dort | Akzeptiert, ergänzt 0002 |
| [0028](0028-poc-ergebnisse-im-zielbetrieb.md) | PoC-Ergebnisse gelten im Zielbetrieb: Booklooker-Preis mit Beleg, Websuche-Vorschlag, Statistik, Fortschritt | Akzeptiert, ersetzt 0017 |
| [0029](0029-laptop-als-comic-rechner.md) | Laptop als Comic-Rechner, WLAN nur als Fallback | Akzeptiert, ergänzt 0001/0002 |
| [0030](0030-kamera-station-per-gphoto2-am-laptop.md) | Erfassung per Canon-Kamera am Laptop (gphoto2) statt Flachbett | Akzeptiert, ergänzt 0007/0018/0029 |
| [0031](0031-installation-per-netzwerkboot-als-alternative-zum-usb-stick.md) | Installation per Netzwerkboot als Alternative zum USB-Stick | Akzeptiert, ergänzt 0002 |
