# Go-Live: vom PoC zum Comic-Rechner

Stand 05.11.2026. Der PoC (`docs/POC.md`) ist abgenommen. Ziel: in der Woche vom **09.–13.11.2026**
auf dem eigenen Comic-Rechner nach den akzeptierten ADRs produktiv gehen (ADR-0001, 0002, 0008, 0009).

## Kernaussage

Es muss **kein Code umziehen**. Alles, was im PoC lief, liegt bereits in diesem Repo:

- Review-Oberfläche mit allem aus dem PoC (Foto-Upload ADR-0018, Papierkorb ADR-0019, Zurückholen
  ADR-0020, Preisvorschlag ADR-0022, Statistik ADR-0023, Live-Fortschritt ADR-0024) steckt im Image
  `comic-helper` (`services/comic-helper/`). Auf dem Comic-Rechner baut Ansible dasselbe Image aus dem
  Repo (Rolle `apps`, podman), statt `docker build` und PoC-Registry.
- Manifeste: der Zielbetrieb nutzt `infra/k3s` direkt, ohne das Overlay `infra/k3s-poc`.
- Workflows: dieselben Exporte aus `workflows/`.

Zu tun sind also: PoC-Sonderregeln für den Zielbetrieb entscheiden (ADRs, `config/pricing.yaml`),
Konten und Infrastruktur anlegen, Rechner installieren, Ende-zu-Ende testen, PoC abbauen.

Die Review-Oberfläche unterscheidet sich danach nur im Zugang:

| | PoC | Zielbetrieb |
| --- | --- | --- |
| Adresse | `http://pro-mini.fritz.box/review/` | `https://comics-01/review/` (LAN, ufw, selbstsigniertes Zertifikat) |
| Anmeldung | keine | `REVIEW_PASSWORD` Pflicht (ADR-0006) |
| Preisquelle vorausgewählt | Booklooker (ADR-0017) | nach Entscheidung E2 |
| Statistik | PoC-Läufe | beginnt leer (neuer Bucket) |

## Entscheidungen bis Freitag, 06.11. (blockieren den Zeitplan)

Entschieden am 05.11.: kein Rückkanal von Shopify, kein Cloudflare-Tunnel (ADR-0025).
Entschieden am 05.11. (ADR-0028): **E2** Booklooker mit Beleg und Websuche-Vorschlag, **E3** Opus bleibt,
**E4** echter Shop, erste Woche `DRAFT`. **E5** neuer Bucket per Terraform. Offen: **E1** Rechner, **E6** Deploy-Key.

| Nr. | Frage | Empfehlung |
| --- | --- | --- |
| E1 | **Rechner:** Mini-PC kaufen oder vorhandenen Office-PC nehmen (`hardware/README.md`)? Scanner jetzt oder später? | Rechner muss Montag da sein, sonst verschiebt sich alles. Scanner darf später kommen: Eingang zunächst per Canon-Kamera am Laptop (ADR-0030), `comics_scanner_enabled: false` bis der Scanner da ist. |
| E2 | **Preisquelle im Zielbetrieb:** ADR-0011 sieht Comicguide vor, die Datenlizenz (Star Media) fehlt aber. Im PoC haben sich Booklooker mit Beleg (ADR-0017) und der automatische Vorschlag (ADR-0022) bewährt. | Neues **ADR-0028 „PoC-Ergebnisse im Zielbetrieb“**: Websuche-Vorschlag und Booklooker mit Beleg gelten im Zielbetrieb, bis eine Comicguide-Lizenz oder API vorliegt. Darin auch 0023 und 0024 für den Zielbetrieb übernehmen. 0017 bekommt den Status `Ersetzt durch ADR-0028`, bei 0022 bis 0024 einen Verweis auf ADR-0028. |
| E3 | **KI-Kosten:** Die Preissuche mit Opus kostet laut Messung etwa 0,29 $ je Comic, bei 2.000 Scans im Monat rund 580 $ plus Erkennung. Sonnet kostet 0,21 $ und weicht im Schnitt um 6 % ab. | `marktpreis.modell` auf Sonnet setzen und nach 4 Wochen mit der Statistik-Seite prüfen. |
| E4 | **Shopify:** echter Shop statt Entwicklungsshop? Produkte als `DRAFT` oder gleich `ACTIVE`? Produktoption oder Produkt je Zustand (ADR-0012 noch `Vorgeschlagen`)? | Echter Shop, App nach `docs/SHOPIFY-EINRICHTUNG.md`. Die erste Woche bleibt `DRAFT`, danach `ACTIVE`. ADR-0012 bleibt wie umgesetzt (Variante je Exemplar) und wird auf `Akzeptiert` gesetzt. |
| E5 | **S3:** PoC-Bucket `comics-scans-roman-0001` weiterverwenden oder neu anlegen? | Neuer Produktiv-Bucket per `terraform apply` (`infra/aws/`), dann liegt er im Terraform-State und enthält keine PoC-Testdaten. Den PoC-Bucket nach dem Go-Live löschen. |
| E6 | **Repo-Zugriff für ansible-pull:** Das Repo ist privat, ansible-pull klont ohne Zugangsdaten (`docs/INSTALL.md`). | Deploy-Key (nur lesen) unter `/root/.ssh/` auf dem Rechner. Ein öffentliches Repo würde auch Konzept-PDF, Preise und Statistikwerte veröffentlichen. |

## Aufgaben im Repo (Montag, 09.11.)

1. ✅ **Push** (05.11.): ansible-pull holt den Stand von GitHub, also zuerst
   pushen und die CI (`test.yml`) grün sehen.
2. ✅ **ADR-0028** geschrieben, Status der alten ADRs nachgezogen (05.11.).
3. ✅ **`config/pricing.yaml`** für den Zielbetrieb kommentiert (05.11.). Werte bleiben: `booklooker`, Opus, `DRAFT`.
   `docs/PREISFINDUNG.md` angeglichen.
4. **Ingress im Zielbetrieb prüfen** (`infra/k3s/base/ingress.yaml`): Er gilt für alle Hostnamen und
   beide Entrypoints, auf dem eigenen Rechner hinter ufw ist das richtig. Testen, dass Foto-Uploads vom
   Handy über https mit selbstsigniertem Zertifikat funktionieren und dass der Name `comics-01` im
   Laden-WLAN auflöst.
5. ✅ **`docs/BETRIEB.md`** um den Workflow-Import mit Aktivierung per CLI ergänzt (05.11.).
6. **ISO-Release** bauen (`build-iso.yml`, ADR-0015, Tag `v*` oder manuell). Vorher im GitHub-Repo unter
   Settings → Secrets and variables → Actions → Variables setzen: `ADMIN_SSH_KEYS` (öffentliche SSH-Schlüssel
   für den Admin-Zugang) und `COMICS_REPO_URL=git@github.com:knievel01/comic-shop.git` (Repo ist privat,
   ansible-pull klont per Deploy-Key, E6).
7. Commit „Go-Live-Vorbereitung (gemäß ADR-0028)“, Status in `docs/PLAN.md` nachziehen.

## Zeitplan

| Tag | Was | Abnahme |
| --- | --- | --- |
| Fr 06.11. | Entscheidungen E1–E6, Hardware beschaffen, BIOS prüfen (USB-Boot, „Power on after AC loss“) | Entscheidungen hier eingetragen |
| Mo 09.11. | Repo-Aufgaben 1–7. AWS: `terraform apply` (Bucket, IAM `comics-app`, `comics-scan-upload`). Shopify-App im echten Shop | CI grün, ISO-Release da, Zugangsdaten im Passwort-Manager |
| Di 10.11. | Rechner nach `docs/INSTALL.md` Schritte 1–7 installieren. Deploy-Key hinterlegen. `/etc/comics/comics.env` befüllen (neues `N8N_ENCRYPTION_KEY`, `HELPER_TOKEN`, `REVIEW_PASSWORD`), `sudo comics-update` | `scripts/verify.sh` grün, Abnahme Phase 2 aus INSTALL.md |
| Mi 11.11. | n8n-Owner anlegen, Credentials „Comic Helper Token“ und „SMTP Comics“, Workflows 01, 02, 04 und 99 importieren und aktivieren. Backup einmal von Hand auslösen und prüfen | Workflows aktiv, Backup liegt in S3 |
| Do 12.11. | E2E-Test mit 10 echten Comics: Foto-Upload (und Scanner, falls da), Review, Bestätigen, Shopify (DRAFT), Testbestellung, dann Bestand 0 in Shopify prüfen, Tagesmail am Freitag um 7 Uhr | alle 10 durch, keine Fehler-Mail von Workflow 99 |
| Fr 13.11. | **Go-Live:** Fachkraft einweisen (`docs/SCANNEN-UND-BESTAETIGEN.md`). PoC zur Sandbox umstellen (siehe unten) | `docs/PLAN.md` aktualisiert |

Puffer: Fällt ein Tag aus, rutscht der Go-Live auf Montag, den 16.11. Der PoC auf pro-mini läuft bis
dahin unverändert weiter und dient als Rückfallebene. Beide Umgebungen teilen sich weder Bucket noch
Datenbank.

## PoC wird Sandbox (nach dem Go-Live)

Der PoC bleibt als Sandbox auf pro-mini (ADR-0027). Jede Änderung läuft zuerst dort, dann auf dem Comic-Rechner.

1. Sandbox auf Testdaten umstellen: eigener Bucket bzw. Präfix (nicht der Produktiv-Bucket aus E5),
   Shopify-Entwicklungsshop, eigene IAM-Schlüssel in `~/.config/comics/comics.env`.
2. Die Datei `comics.env` im Repo-Wurzelverzeichnis (ignoriert, aber mit Werten und Rechten 664) löschen
   oder auf Rechte 600 setzen.
3. Testentwürfe im Shopify-Shop löschen, falls der PoC sie im echten Shop angelegt hat.
4. In `docs/PLAN.md` die PoC-Zeile auf „Sandbox“ setzen.

## Risiken

- **Hardware:** Die ISO wurde noch nie auf echter Hardware installiert (PLAN, offener Punkt 8). Reserve:
  Installation am Dienstag, Puffer bis Montag, den 16.11.
- **Scanner:** SANE-Kompatibilität ungeprüft (`hardware/scanner-linux.md`). Der Foto-Upload überbrückt das.
- **Self-signed Zertifikat:** Jedes Handy zeigt einmal eine Warnung. Für den Laden akzeptabel, sonst
  später ein eigenes Zertifikat (eigenes ADR).
