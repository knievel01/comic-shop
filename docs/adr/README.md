# Architecture Decision Records

**Verbindliche Grundlage für alle Arbeiten in diesem Repo** (siehe [ADR-0000](0000-adrs-als-grundlage.md) und `CLAUDE.md`).
Ein ADR beschreibt den **aktuellen Stand** einer tragenden Entscheidung. Änderungen werden im ADR nachgezogen, der
Verlauf steht in Git. Neue Entscheidung: zuerst prüfen, ob ein bestehendes ADR sie aufnehmen kann, sonst
[`_vorlage.md`](_vorlage.md) verwenden.

| Nr. | Titel | Status |
| --- | --- | --- |
| [0000](0000-adrs-als-grundlage.md) | ADRs als verbindliche Entscheidungsgrundlage | Akzeptiert |
| [0001](0001-ein-laptop-fuer-scan-station-und-server.md) | Ein Laptop für Scan-Station und Server | Akzeptiert (vorläufig) |
| [0002](0002-autoinstall-iso-und-ansible-pull.md) | Reproduzierbare Installation: Autoinstall-ISO und ansible-pull | Akzeptiert |
| [0003](0003-geheimnisse-nie-in-repo-oder-image.md) | Geheimnisse nie in Repo oder Image | Akzeptiert |
| [0004](0004-s3-als-einziger-zustandsspeicher-keine-comic-datenbank.md) | S3 als einziger Zustandsspeicher, keine Comic-Datenbank | Akzeptiert |
| [0005](0005-fachlogik-im-dienst-comic-helper-n8n-orchestriert.md) | Fachlogik im Dienst comic-helper, n8n orchestriert | Akzeptiert |
| [0006](0006-review-oberflaeche-im-comic-helper-statt-n8n-formular.md) | Review-Oberfläche im comic-helper statt n8n-Formular | Akzeptiert |
| [0007](0007-erfassung-als-pdf-upload-per-sync-skript.md) | Erfassung als 2-seitige PDF, Upload per Sync-Skript mit UUID | Akzeptiert |
| [0008](0008-n8n-als-einzelinstanz-mit-postgres-auf-k3s.md) | n8n als Einzelinstanz mit Postgres auf K3s | Akzeptiert |
| [0010](0010-erkennung-mit-claude-ximilar-nur-nach-vergleichstest.md) | Erkennung mit Claude, Ximilar nur nach Vergleichstest | Vorgeschlagen |
| [0011](0011-preisfindung-comicguide-skala-booklooker-ohne-scraping.md) | Preisfindung: Comicguide-Skala, Booklooker-Marktpreis mit Beleg, kein Scraping | Akzeptiert |
| [0012](0012-shopify-anbindung-variante-je-exemplar.md) | Shopify-Anbindung: Variante je Exemplar, Sammelposten, Dev-Dashboard-App | Akzeptiert (Zustand als Option offen) |
| [0025](0025-kein-internetzugang-zugriff-nur-im-lan.md) | Kein Zugang aus dem Internet, Zugriff nur im LAN, Verkäufe nur in Shopify | Akzeptiert |
| [0027](0027-sandbox-zuerst-rollout-per-ssh.md) | Sandbox zuerst, dann Rollout per SSH; Sandbox und Produktion teilen keine Daten | Akzeptiert |

## Frühere Nummern

Am 2026-11-13 wurden 41 ADRs auf 14 zusammengeführt. Verweise auf entfernte Nummern (Commit-Messages, alte Doku) gehen
hier hin; der Originaltext steht in der Git-Historie vor diesem Datum.

| Früher | Jetzt | Früher | Jetzt |
| --- | --- | --- | --- |
| 0009 Tunnel für Webhooks | 0025 | 0026 Sammelposten | 0012 |
| 0013 SKU mit Kurz-ID | 0012 | 0028 PoC-Ergebnisse im Zielbetrieb | 0011 (Preise), 0012 (Entwurf-Phase), 0006/0004 |
| 0014 erst Shopify, dann S3 | 0004 | 0029 Laptop | 0001 |
| 0015 ISO in Teilen | 0002 | 0030 Kamera | 0007 |
| 0016 Order-Webhooks | 0025 | 0031 Netzboot | 0002 |
| 0017 Booklooker-Preis (PoC) | 0011 | 0032 Cinnamon | 0001 |
| 0018 Foto-Upload | 0007 | 0033, 0035 PoC-/Produktiv-Bucket | 0027 |
| 0019 Papierkorb | 0004 | 0034 http ohne Passwort | 0025 |
| 0020 Zurückholen | 0006 | 0036, 0037 `kubectl` für `scan` | 0025 |
| 0021 Dev-Dashboard-App | 0012 | 0038, 0039 Sandbox Lima / OrbStack | 0027 |
| 0022 Preisvorschlag per Websuche | 0011 | 0040 Rollout per SSH | 0027 |
| 0023 Statistik | 0006 | 0024 Fortschritt als S3-Tag | 0004 |
