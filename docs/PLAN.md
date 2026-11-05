# Umsetzungsplan: Comic-Shop-Automatisierung (n8n + S3 + Shopify)

## Umsetzungsstand (27.10.2026)

Legende: ✅ im Repo umgesetzt und automatisch getestet · 🟡 im Repo umgesetzt, Test braucht echte
Hardware/Konten · ⬜ offen (Entscheidung oder Handarbeit nötig)

| Phase | Stand | Wo | Noch zu tun |
| --- | --- | --- | --- |
| 1 Repo | ✅ | `CLAUDE.md`, `.gitignore`, `.env.example` | – |
| 2 OS/ISO | 🟡 | `os/`, `scripts/verify.sh`, `docs/INSTALL.md` | ISO auf echter Hardware bauen und installieren, Stromausfall-Test, SANE-Prüfung des Scanners (⬜ Kaufentscheidung) |
| 3 K3s/n8n | 🟡 | `infra/k3s/` | Rollout auf dem Rechner, Cloudflare-Tunnel einrichten |
| 4 AWS | 🟡 | `infra/aws/` (terraform validate ok) | `terraform apply` mit Admin-Konto |
| 5 Ingest | ✅ | Rolle `sync`, Workflow 01, `comic-helper` | in n8n 2.46 getestet (Docker) |
| 6 Erkennung/Preis | 🟡 | `recognition.py`, `pricing.py`, `config/pricing.yaml`, `scripts/vergleichstest.py` | ⬜ Vergleichstest mit 50 Comics, Modellwahl, Schwelle; ⬜ Datenlizenz Star Media, Anfrage AbeBooks |
| 7 Review | ✅ | `comic-helper` `/review/` | Status als S3-Tag, überlebt Neustarts (ADR-0006); Live-Fortschritt von Workflow 01 auf der Kachel (ADR-0024); Statistik Kosten/Einsparung (ADR-0023) |
| 9 Shopify | 🟡 | `shopify.py`, Workflow 02 | gegen Fake-API getestet; App im Dev Dashboard (ADR-0021, docs/SHOPIFY-EINRICHTUNG.md), im PoC-Shop als Entwurf getestet: Comic bestätigt, Produkt angelegt, Workflow 02 (aktiv) verschiebt nach `aktiv/`; ⬜ Kanal veröffentlichen, ⬜ Entscheidung Produktoption vs. Produkt je Zustand |
| 8 Metadaten | ✅ | `finalize`, `storage.py` | – |
| 10 Verkauf | ✅ | `webhooks.py`, Workflow 03 | in n8n getestet inkl. Doppelzustellung; Webhooks in Shopify registrieren |
| 11 Tagesmail | ✅ | `report.py`, Workflow 04 | SMTP-Credential anlegen |
| 12 Betrieb | 🟡 | `docs/BETRIEB.md`, `docs/SCANNEN-UND-BESTAETIGEN.md`, Workflow 99, CI | E2E mit 50 Comics, Restore-Test, Preise nach 100 Verkäufen |

PoC (01.11.2026): Machbarkeitstest von Postgres, n8n und `comic-helper` im vorhandenen K3s des
Entwickler-Rechners (`infra/k3s-poc/`, `scripts/poc-host-k3s.sh`, Anleitung `docs/POC.md`). Vorübergehende
Testumgebung ohne Tunnel, Scanner, Sync und Ansible, kein ADR; ersetzt nicht den Rollout aus Phase 2/3.

Go-Live (05.11.2026): PoC abgenommen, Rollout auf den Comic-Rechner in der Woche ab 09.11.2026,
Entscheidungen, Aufgaben und Zeitplan in `docs/GO-LIVE.md`.

Abweichungen vom Plan und Begründungen: ADRs in `docs/adr/` (v. a. 0005, 0006, 0013). Die wichtigsten:
Fachlogik im Python-Dienst `comic-helper` statt in n8n-Nodes; Review-Oberfläche dort statt n8n-Form/Wait;
SKU endet auf 12 Stellen der Exemplar-UUID statt auf a/b/c (der Buchstabe bleibt Shopify-Option).

Offene Punkte aus der Liste unten: 1 und 2 (Architekturdokument liegt nicht im Repo),
7 und 8 (Hardware), 9 und 10 (Anfragen), 11 (Vergleichstest).

---

Dieser Plan ist als Arbeitsgrundlage für Claude Code gedacht. Jede Phase hat Ziel, Aufgaben und Abnahmekriterien. Phasen der Reihe nach abarbeiten, nach jeder Phase committen.

## 0. Zielbild

- Scanner (A3-Flachbett) erzeugt pro Comic eine zweiseitige PDF (Cover + Rückseite) und legt sie in S3 ab.
- n8n (auf lokalem K3s) erkennt Titel, Ausgabe und Verlag (Claude und/oder Ximilar, Entscheidung per Vergleichstest).
- Zustand wird nach der Comicguide-Skala 0 bis 4 bewertet. Pro Comic wird nur der Comicguide-Preis für Zustand 1 benötigt, alle anderen Zustände und Sepps Aufschlag berechnet n8n.
- Eine Fachkraft bestätigt im n8n-Formular Titel, Zustand und den Zustand-1-Preis (bei noch lieferbaren Titeln automatisch aus dem Coverpreis).
- Alle Metadaten liegen als S3-Objekt-Metadaten am Bild. Es gibt keine eigene Comic-Datenbank.
- Shopify ist Quelle der Wahrheit für den Lagerbestand. Pro Exemplar gibt es eine eigene Variante mit eindeutiger SKU (Variante B).
- Ein Verkaufs-Webhook verschiebt das zur SKU gehörende Bild in den Ordner `verkauft/`.
- Täglich um 7 Uhr geht eine Sammel-Mail raus (gescannt, offen, sicher vs. Nachkontrolle).

Mengenrahmen: ca. 2.000 Scans pro Monat, Gesamtbestand 20.000 bis 40.000 Comics.

## 1. Repo und Konventionen

Aufgaben:
- Git-Repo anlegen, Struktur:
  ```
  /os/                 Autoinstall-Konfiguration, ISO-Build, Ansible-Rollen
  /infra/k3s/          Kubernetes-Manifeste bzw. Helm-values
  /infra/aws/          Terraform oder CLI-Skripte für S3 und IAM
  /workflows/          exportierte n8n-Workflows als JSON
  /scripts/            Python-/Node-Hilfsskripte
  /docs/               Architektur, Betrieb, INSTALL.md (kompletter Installationsflow)
  CLAUDE.md            Konventionen für Claude Code
  ```
- `CLAUDE.md` mit Regeln: keine Secrets im Repo, Workflows nach jeder Änderung exportieren und committen, deutsche Doku, Kommentare im Code englisch.
- `.env.example` mit allen benötigten Variablen (ohne Werte).

Abnahme: Repo steht, `.gitignore` schließt `.env` und Exporte mit Credentials aus.

## 2. Hardware und Betriebssystem (Scan-/Server-Rechner)

Ziel: Ein alter Office-Rechner wird reproduzierbar zum Comic-Rechner. Der komplette Installationsflow steht im Git-Repo, sodass der Rechner im Notfall in unter einer Stunde neu aufgesetzt werden kann.

### 2.1 Hardware-Check und Grundentscheidungen

- Mindestanforderung: 64-Bit-CPU mit 4 Kernen, 8 GB RAM (n8n, Postgres und K3s laufen mit 4 GB, aber die Scan-Oberfläche und PDF-Umwandlung brauchen Luft), SSD (kein Spinning Disk), 120 GB oder mehr, Gigabit-LAN.
- BIOS/UEFI: Boot von USB aktivieren, "Power on after AC loss" einschalten, Secure Boot nach Bedarf. Optional eine kleine USV.
- **Entscheidung 1: Ein Rechner für alles oder zwei?** Scan-Station (mit Oberfläche für die Schülerkräfte) und K3s-Server auf derselben Maschine ist am einfachsten. Sauberer wäre eine getrennte Aufteilung: Scan-Rechner mit Desktop, Server headless. Startempfehlung: ein Rechner, Desktop minimal (XFCE), K3s läuft als Systemdienst im Hintergrund. Später trennbar, weil alles im Repo als Ansible-Rollen modular ist.
- **Entscheidung 2: Linux-Treiber für den Scanner vorab prüfen.** Vor dem Kauf in der SANE-Geräteliste (sane-project.org, "Supported Devices") nachsehen, ob Plustek OpticSlim 1180/1680 beziehungsweise Epson V600 sauber unterstützt sind und wie gut. Das ist eine harte Voraussetzung. Falls ein Modell nicht passt, bleibt als Ausweg ein separater Windows-Scan-Rechner, der nur per Sync nach S3 hochlädt.

### 2.2 Betriebssystem und "fertiges Image"

Zielsystem: Ubuntu Server 24.04 LTS (lange Support-Laufzeit, gute Hardware-Unterstützung, K3s und SANE sind gut dokumentiert).

Zwei Wege, empfohlen ist Weg A:

- **Weg A (empfohlen): Autoinstall-ISO.** Die offizielle Ubuntu-Server-ISO wird per Skript um eine Autoinstall-Konfiguration ergänzt (`user-data` und `meta-data`). Der Rechner bootet vom USB-Stick und installiert sich ohne Rückfragen. Das passt auf unterschiedliche alte Hardware, weil Treiber und Festplattenaufteilung erst beim Installieren ermittelt werden. Die ISO wird nicht ins Git eingecheckt, sondern in einer CI-Pipeline (GitHub Actions) gebaut und als Release-Artefakt zum Download bereitgestellt.
- **Weg B (nur bei identischer Hardware): Vorgebackenes Disk-Image.** Mit Packer wird ein komplettes Festplatten-Image gebaut und per `dd` auf die SSD geschrieben. Das ist schneller beim Ausrollen, aber bei alten Office-Rechnern fragil (BIOS vs. UEFI, Plattengröße, Netzwerk-Schnittstellennamen, Treiber). Nur sinnvoll, wenn später mehrere baugleiche Rechner entstehen.

Wichtig zu "all die benötigten Pakete im Image": Die ISO enthält die Konfiguration und lädt die Pakete beim ersten Boot nach. So bleibt das Image klein, aktuell und reproduzierbar. Wer wirklich offline installieren will, kann zusätzlich einen lokalen Paket-Mirror bzw. ein K3s-Airgap-Bundle beilegen.

### 2.3 Inhalt der Konfiguration (alles im Repo unter `/os/`)

- `autoinstall/user-data`: Sprache `de_DE`, Tastatur `de`, Zeitzone `Europe/Berlin`, Hostname z. B. `comics-01`, Speicher-Layout (ganze SSD, LVM optional), Benutzer, SSH nur per Schlüssel, Basispakete.
- Basispakete: `openssh-server git curl ansible python3-venv sane-utils poppler-utils imagemagick unattended-upgrades ufw` sowie die AWS CLI (per offiziellem Installer, nicht per apt) und die Scan-Software (NAPS2 oder Hersteller-Software, Verfügbarkeit unter Linux prüfen).
- `late-commands`: Repo klonen und beim ersten Start automatisch `ansible-pull` ausführen.
- `ansible/roles/`:
  - `base`: Benutzer, SSH-Härtung, Firewall (ufw), automatische Sicherheitsupdates, Zeitsynchronisation.
  - `desktop`: minimaler XFCE-Desktop für die Scan-Station, Auto-Login für den Scan-Benutzer (optional).
  - `scanner`: SANE-Konfiguration, udev-Regeln, Scan-Benutzer in Gruppe `scanner`, Scan-Software, Test-Skript, das einen Probe-Scan erzeugt.
  - `sync`: Skript plus systemd-Timer, das neue PDFs aus dem Scan-Ordner nach `s3://…/eingang/` hochlädt (AWS CLI Sync).
  - `k3s`: K3s in fest gepinnter Version installieren, `kubectl` einrichten, Kubeconfig absichern, Datenverzeichnis auf der lokalen Platte (local-path-Storage).
  - `apps`: Manifeste aus `/infra/k3s/` anwenden (n8n, Postgres, Ingress).
  - `backup`: systemd-Timer für `pg_dump` und Workflow-Export nach S3.
- `build-iso.sh`: baut aus der Ubuntu-ISO (Prüfsumme verifizieren) und der Autoinstall-Konfiguration die fertige ISO (z. B. mit `xorriso`).
- `.github/workflows/build-iso.yml`: baut die ISO bei jedem Release-Tag und hängt sie als Download an.

### 2.4 Geheimnisse gehören nicht ins Image

Die ISO ist ein öffentlich ladbares Artefakt, deshalb dürfen darin weder AWS-Schlüssel noch Ximilar-Token, Shopify-Token, `N8N_ENCRYPTION_KEY` noch Passwörter stehen. Stattdessen: Nach der Installation werden die Geheimnisse einmalig auf den Rechner gebracht, entweder per Hand in eine `.env`-Datei (Rechte 600) oder verschlüsselt im Repo mit SOPS und age (privater Schlüssel liegt nur auf dem Rechner und im Passwort-Manager). Ansible erzeugt daraus die Kubernetes-Secrets.

### 2.5 Installationsflow (wird in `docs/INSTALL.md` ausführlich dokumentiert)

1. Aktuelle ISO aus dem Release herunterladen, Prüfsumme prüfen.
2. USB-Stick beschreiben (balenaEtcher oder `dd`).
3. BIOS-Einstellungen setzen (USB-Boot, Power on after AC loss).
4. Vom Stick booten, Autoinstall läuft durch, Rechner startet neu.
5. Erster Boot: `ansible-pull` richtet Pakete, Scanner, K3s und Apps ein (Protokoll unter `/var/log/`).
6. Geheimnisse einspielen (`.env` oder SOPS-Schlüssel).
7. Prüfskript `scripts/verify.sh` ausführen: K3s bereit, n8n erreichbar, Probe-Scan erzeugt PDF, Upload nach S3 funktioniert, Backup-Timer aktiv.

### 2.6 Abnahme

- Komplettinstallation von leerer SSD bis grünem `verify.sh` dauert unter 60 Minuten und ist ohne manuelle Eingriffe außer Schritt 3 und 6 möglich.
- Stromausfall-Test: Netzstecker ziehen, wieder einstecken, Rechner startet, K3s und n8n kommen von allein hoch, keine Workflows gehen verloren.
- Neuinstallation aus dem Repo auf demselben Rechner wiederholt das Ergebnis reproduzierbar.
- Probe-Scan mit dem tatsächlich gekauften Scanner funktioniert unter Linux.

## 3. Infrastruktur: n8n auf K3s

Aufgaben:
- Namespace `comics` anlegen.
- Postgres für n8n deployen (StatefulSet oder vorhandener Cluster-Postgres, PVC auf lokaler Festplatte). Das ist nur die interne n8n-Datenbank, nicht für Comic-Daten.
- n8n deployen (Deployment, Service, Ingress mit TLS). Zunächst Single-Instance, Queue-Mode ist bei 2.000 Scans pro Monat nicht nötig.
- Wichtige Umgebungsvariablen: `N8N_ENCRYPTION_KEY` (als Secret, extern sichern!), `WEBHOOK_URL`, `DB_TYPE=postgresdb`, `GENERIC_TIMEZONE=Europe/Berlin`.
- Webhook-Erreichbarkeit für Shopify klären (öffentliche URL, z. B. Cloudflare Tunnel oder Reverse Proxy). Nur die Webhook-Pfade freigeben, die Editor-UI nicht.
- Backup: täglicher `pg_dump` plus Export der Workflows ins Repo.

Abnahme: n8n-UI erreichbar, Test-Webhook von außen erreichbar, Neustart des Pods verliert keine Workflows.

## 4. AWS: S3 und IAM

Aufgaben:
- Bucket in `eu-central-1`, Public Access komplett blockiert, Versioning an (Schutz vor versehentlichem Überschreiben), SSE-S3 Verschlüsselung.
- Präfix-Struktur:
  ```
  eingang/       frisch gescannte PDFs, noch nicht bestätigt
  aktiv/         bestätigt und in Shopify angelegt
  verkauft/      verkaufte Exemplare
  ```
- IAM-User oder Rolle nur für diesen Bucket (Least Privilege: Get, Put, Copy, Delete, List auf den Bucket).
- Lifecycle: Noncurrent Versions nach 30 Tagen löschen, damit die Kosten gegen null bleiben.

Abnahme: Test-Upload per CLI klappt, Zugriff von außen ohne Credentials scheitert.

## 5. Scan-Ingest

Aufgaben:
- Scan-Software festlegen (NAPS2 oder Epson-/Plustek-Software). Ziel: pro Comic eine PDF mit zwei Seiten.
- Dateinamen-Schema festlegen, z. B. `{UUID}.pdf`. Die UUID ist die spätere eindeutige Exemplar-ID.
- Ablage nach `eingang/`. Entscheidung treffen, ob der Upload per s3fs-Mount, per AWS CLI Sync oder per Skript auf dem Scan-Rechner läuft. Empfehlung: Sync-Skript auf dem Scan-Rechner, weil das robuster ist als ein FUSE-Mount im Cluster.
- n8n-Trigger: S3-Polling (Schedule alle 1 bis 5 Minuten, neue Keys unter `eingang/`) oder S3-Event-Benachrichtigung an einen Webhook. Polling ist einfacher und reicht hier.

Abnahme: Eine Test-PDF in `eingang/` startet den Workflow genau einmal.

## 6. Erkennung und Preisfindung

### 6.1 Vergleichstest vor der Entscheidung

Ximilar deckt laut eigener Angabe vor allem US-Verlage (Marvel, DC, Dark Horse, Image u. a.) und japanische Manga ab, deutsche Verlage wie Ehapa, Carlsen oder Bastei werden nicht genannt. Die Ximilar-Preisdaten kommen aus eBay, Mercari und Rakuten, also nicht vom deutschen Markt, und werden deshalb nicht für die Preisfindung genutzt. Für die Erkennung zuerst testen:

- 50 Comics auswählen, die Sepps Sammlung repräsentieren (deutsch und US, alt und neu, Hefte und Alben).
- Jeden Comic durch die Ximilar-Demo bzw. API und durch Claude (Cover und Rückseite) schicken.
- Pro Weg festhalten: richtig erkannt, falsch erkannt, nicht erkannt. Zusätzlich den deutschen Anteil der Sammlung schätzen.
- Entscheidung: nur Claude, nur Ximilar oder Hybrid (Claude für deutsche Comics, Ximilar zusätzlich für US-Comics und Manga).

### 6.2 Erkennung

- PDF-Seiten in Bilder umwandeln (Python-Skript oder Tool im Cluster).
- Claude liest strukturiert aus Cover und Rückseite: Titel, Heftnummer, Verlag, Jahr, Sprache, ISBN bzw. EAN, aufgedruckter Originalpreis. Pro Feld eine Sicherheitsangabe. Im Prompt festlegen: Nicht lesbare Felder bleiben leer, es wird nichts geraten.
- Mit ISBN oder EAN ist der Treffer eindeutig. Ohne Barcode Abgleich gegen eine Comic-Datenbank (Comicguide, alternativ Grand Comics Database).
- Optional Ximilar parallel für US-Comics und Manga (Token als n8n-Credential, Doku: https://docs.ximilar.com/collectibles/recognition).
- Ergebnis normalisieren: Titel, Ausgabe, Verlag, Sicherheit, Rohantworten.
- Konfidenzschwelle festlegen (Startwert z. B. 80 %): darüber "sicher", darunter "Nachkontrolle".

### 6.3 Preisfindung (nach Sepps Praxis)

Sepp nutzt heute Comicguide als Hauptquelle, ZVAB.de und Booklooker als zusätzlichen Preisindex und den gedruckten Katalog bei Unklarheiten. Laut Sepp liegen die Comicguide-Preise in der Regel zu niedrig, man kann fast immer 50 % aufschlagen.

**Rechercheergebnis zu den Quellen:**

| Quelle | Automatischer Zugriff | Bedeutung für uns |
| --- | --- | --- |
| Comicguide (comicguide.de, Star Media) | Keine API gefunden. Laut Impressum ist Data Mining nach § 44b UrhG ausdrücklich untersagt, Weiterverwendung nur mit schriftlicher Genehmigung. | Kein Scraping. Manuelle Abfrage per Direktlink, parallel Datenlizenz bei Star Media anfragen (info@comicguide.de). Abdeckung: über 140.000 Titel, ca. 95 % aller deutschsprachigen Comics seit 1945. |
| Booklooker | API vorhanden, aber nur für Verkäufer (Artikel, Datei-Upload, Bestellungen). Keine Preissuche über fremde Angebote. | Nur Direktlink zur Suche. Optional später zweiter Verkaufskanal (6,9 % Provision, keine Grundgebühr). |
| ZVAB (seit 2011 AbeBooks/Amazon) | Früher Partner-Such-API, AbeBooks hatte eine Search-Web-Services-API mit Zugangsschlüssel. Aktueller Stand unklar. | Direktlink zur Suche. Bei AbeBooks anfragen, ob es noch API-Zugänge gibt. |

**Zustandsskala nach Comicguide (übernehmen statt eigener Güte 1 bis 5):**

| Zustand | Bezeichnung | Faktor zu Zustand 1 |
| --- | --- | --- |
| 0 | perfekt | ca. 150 % |
| 1 | sehr gut | 100 % (Basispreis) |
| 2 | gut | ca. 40 % |
| 3 | noch sammelwürdig | ca. 20 % |
| 4 | zum Wegwerfen zu schade | ca. 10 % |

Comicguide beschreibt zusätzlich Zwischenstufen (0-1, 1-2 usw.), nennt dafür aber keine Preise. Startentscheidung: nur ganze Stufen verwenden. Unvollständige Comics ("Zustand 5") werden nicht über den Shop verkauft oder separat als Konvolut behandelt.

**Preisformel:**

```
Basis (Zustand 1) = Comicguide-Preis Z1
                    oder, bei noch lieferbaren Titeln: Coverpreis × 2/3
Preis             = Basis × Zustandsfaktor × Aufschlag (Start 1,5)
                    danach auf glatte Shop-Preise runden (z. B. ,50 / ,99)
```

- Zustandsfaktoren, Aufschlag und Rundung sind zentrale Konfigurationswerte (n8n-Variablen oder Config-Datei im Repo), damit Sepp sie anhand echter Verkäufe nachjustieren kann.
- Noch lieferbare Titel: Claude liest den Coverpreis vom Scan, die Basis wird automatisch berechnet (Comicguide setzt Zustand 1 bei lieferbaren Comics mit 2/3 des Coverpreises an). Achtung bei alten DM-Preisen: Diese Regel nur bei Euro-Coverpreisen und aktuellen Titeln anwenden.
- Alle anderen Titel: Das Review-Formular zeigt Direktlinks zur Suche bei Comicguide, ZVAB und Booklooker mit vorausgefülltem Titel und Heftnummer. Die Fachkraft trägt nur den Comicguide-Preis für Zustand 1 ein, alles Weitere rechnet n8n.
- ZVAB und Booklooker dienen der Fachkraft als Plausibilitätsprüfung. Dort stehen Angebotspreise, keine tatsächlich erzielten Verkaufspreise.
- Kein Comicguide-Eintrag: Hinweis "Katalog prüfen", Basispreis aus dem gedruckten Katalog eintragen.
- Gespeichert werden Preisquelle (`comicguide`, `coverpreis`, `katalog`, `manuell`), Basispreis Z1, Faktor und Endpreis, damit jeder Preis nachvollziehbar bleibt.
- Comicguide-Coverabbildungen und -Texte dürfen nicht in den Shop übernommen werden. Im Shop nur eigene Scans verwenden.

**Parallel anfragen:**
1. Star Media: Datenlizenz oder Export für Titel und Sammlerpreise. Damit ließe sich Schritt "Z1-Preis eintragen" vollständig automatisieren.
2. AbeBooks/ZVAB: aktueller Stand eines Such-API-Zugangs.

Abnahme: Mit 20 Test-Comics ist die Trefferquote der Erkennung dokumentiert, die berechneten Preise weichen nicht stärker als vereinbart von Sepps eigener Einschätzung ab, und die Fachkraft braucht pro nicht lieferbarem Comic höchstens eine Eingabe für den Preis. Fehlerfälle (API-Fehler, kein Treffer) landen in einem Fehlerpfad statt den Workflow abzubrechen.

## 7. Review-Formular (Human-in-the-Loop)

Aufgaben:
- n8n-Formular bzw. Wait-Node mit Formular: zeigt Bilder und KI-Vorschlag. Felder: Titel bestätigen oder korrigieren, Zustand (Comicguide-Skala 0 bis 4, mit Kurzbeschreibung je Stufe als Hilfe), Zustand-1-Preis (vorausgefüllt bei lieferbaren Titeln, sonst mit Direktlinks zu Comicguide, ZVAB und Booklooker), Freitext. Der berechnete Endpreis wird live angezeigt und kann überschrieben werden.
- Status "offen" und "bestätigt" sauber abbilden. Offene Fälle dürfen nicht verloren gehen, auch wenn n8n neu startet. Prüfen, ob Wait-Nodes den Neustart überleben. Falls nicht, Status als S3-Präfix oder Tag abbilden.

Abnahme: Ein Durchlauf mit Bestätigung und einer mit Korrektur funktioniert, ein Pod-Neustart zwischen Scan und Bestätigung verliert nichts.

## 8. Metadaten in S3 schreiben

Aufgaben:
- Nach der Bestätigung Metadaten setzen: `titel`, `ausgabe`, `verlag`, `ki-konfidenz`, `zustand` (0 bis 4), `preis-basis-z1`, `preis-quelle`, `preis-final`, `exemplar-id` (SKU), später `shopify-variant-id`. Limit beachten: ca. 2 KB pro Objekt, Werte nur ASCII oder URL-kodiert.
- Wichtig: S3-Metadaten sind nachträglich nicht änderbar, nur per `CopyObject` auf sich selbst mit `MetadataDirective=REPLACE`. Das Schreiben also erst nach der Freigabe und nach dem Shopify-Anlegen (damit die Variant-ID schon bekannt ist) oder bewusst als zweiten Schritt per Copy.
- Zu verifizieren: Ob die n8n-S3-Node benutzerdefinierte Metadaten unterstützt. Falls nicht, kleinen Python-Helfer (boto3) bauen, entweder als Code-Node (Python-Unterstützung und erlaubte Module prüfen) oder als kleiner HTTP-Dienst im Cluster, den n8n aufruft. Meine Empfehlung ist der HTTP-Dienst, weil er testbar und unabhängig von n8n-Sandbox-Grenzen ist.
- Beim Verschieben nach `aktiv/` bleiben die Metadaten erhalten, wenn per Copy mit `MetadataDirective=COPY` gearbeitet wird.

Abnahme: `aws s3api head-object` zeigt alle Metadaten am bestätigten Objekt.

## 9. Shopify-Anbindung (Variante B: Einzel-SKU pro Exemplar)

Aufgaben:
- Custom App im Shopify-Admin anlegen, Scopes: Produkte und Inventar (lesen und schreiben), Bestellungen lesen. Token als n8n-Credential.
- Datenmodell: Ein Produkt je Titel und Ausgabe. Pro Exemplar eine Variante mit Menge 1 und SKU wie `asterix-xy-z3-a` (z = Zustand nach Comicguide). Shopify verlangt eindeutige Options-Kombinationen, daher z. B. Option 1 `Zustand` (0 bis 4, im Shop mit Bezeichnung wie "1 – sehr gut") und Option 2 `Exemplar` (a, b, c). Die Zustandsbeschreibungen in eigenen Worten im Shop erklären, nicht von Comicguide kopieren. Limits für Varianten pro Produkt und Anzahl der Optionen in der aktuellen Shopify-API-Version prüfen.
- Abgleich: Produkt per Titel/Ausgabe suchen (GraphQL), vorhanden: neue Variante anhängen, sonst Produkt mit erster Variante anlegen. Preis ist der in Phase 6.3 berechnete und im Formular bestätigte Endpreis.
- Offen aus dem Dokument: Kommentar zu Produktoption vs. separate Produkte je Zustand klären, bevor dieser Schritt gebaut wird.
- Idempotenz: Gleiche UUID darf nicht zweimal angelegt werden (SKU-Lookup vor dem Anlegen).

Abnahme: Ein bestätigtes Exemplar erscheint im Testshop mit korrekter SKU, Preis und Bestand 1.

## 10. Verkaufs-Webhook

Aufgaben:
- Shopify-Webhook `orders/paid` (oder `orders/create`) an n8n. Der Order-Payload enthält die Line Items mit SKU, damit ist die Zuordnung direkt möglich. (`inventory_levels/update` liefert nur die Inventory-Item-ID und braucht einen zusätzlichen Lookup, daher ist der Order-Webhook hier die bessere Wahl.)
- Webhook-Signatur (HMAC) prüfen.
- Pro Line Item: Objekt über die SKU finden (SKU ist Teil des Keys bzw. der Metadaten), per Copy nach `verkauft/` verschieben, Original löschen.
- Sonderfälle: Stornierung oder Retoure (`orders/cancelled`, Refund) verschiebt zurück nach `aktiv/`. Doppelte Webhook-Zustellung muss folgenlos bleiben.

Abnahme: Testbestellung verschiebt genau das richtige Bild, ein erneut gesendeter Webhook ändert nichts.

## 11. Tägliche Sammel-Mail (7 Uhr)

Aufgaben:
- Schedule-Trigger 07:00 (Europe/Berlin).
- Zählen: gescannt gesamt, offene Bewertungen, davon sichere KI-Treffer vs. Nachkontrolle (Beispiel: 60 gescannt, 58 offen, 50 sicher, 10 Nachkontrolle).
- Mailversand über SMTP- oder Mail-Node, Empfänger konfigurierbar.

Abnahme: Mail kommt pünktlich, Zahlen stimmen mit S3-Stand überein.

## 12. Test, Betrieb, Übergabe

Aufgaben:
- End-to-End-Test mit 50 echten Comics inklusive Verkauf einer Testbestellung.
- Monitoring: Fehler-Workflow in n8n, der bei Ausfällen eine Mail schickt.
- Kosten kontrollieren: Claude-API bzw. Ximilar-Credits (je nach Ergebnis des Vergleichstests), S3 und Transfer.
- Preisfaktoren nach den ersten 100 Verkäufen mit Sepp überprüfen und nachjustieren.
- Doku für Sepp und die Schülerkräfte: eine Seite "Scannen und Bestätigen".
- Backup-Test: n8n aus Repo und Dump auf frischem K3s wiederherstellen.

## Offene Punkte und Risiken

1. Preisangabe zum Epson V600 im Architekturdokument korrigieren (340 bis 430 € statt 250 bis 350 €). Bei A3-Bedarf gilt ohnehin Plustek OpticSlim 1180 oder 1680.
2. Entscheidung Produktoption vs. separate Produkte je Zustand (Shopify-Kommentar im Architekturdokument). Architekturdokument außerdem von Güte 1 bis 5 auf Comicguide-Skala 0 bis 4 umstellen.
3. S3-Metadaten aus n8n schreiben: Machbarkeit der n8n-S3-Node prüfen, sonst boto3-Dienst.
4. s3fs/FUSE im Cluster braucht privilegierte Container und ist für Metadaten und Konsistenz heikel. Sync-Skript oder direkte API-Zugriffe bevorzugen.
5. Wait-Nodes und Neustarts: Persistenz offener Review-Fälle absichern.
6. Shopify-Varianten-Limits bei vielen Exemplaren desselben Titels prüfen.
7. Linux-Unterstützung des gewählten Scanners (SANE) vor dem Kauf verifizieren, sonst separaten Scan-Rechner einplanen.
8. Altes Office-Hardware kann bei BIOS, WLAN oder Netzwerkkarte Eigenheiten haben: Autoinstall-ISO vorab auf dem echten Gerät testen.
9. Comicguide verbietet Data Mining. Datenlizenz bei Star Media anfragen, bis dahin Z1-Preis manuell per Direktlink. Kein Scraping.
10. ZVAB/AbeBooks: aktuellen Stand eines Such-API-Zugangs anfragen. Booklooker-API ist nur Verkäufer-API, optional als zweiter Verkaufskanal prüfen.
11. Ximilar-Abdeckung für deutsche Comics ist ungewiss, Entscheidung erst nach dem Vergleichstest (6.1).
12. `N8N_ENCRYPTION_KEY` separat sichern, sonst sind alle Credentials nach einem Datenverlust unbrauchbar.

## Reihenfolge-Empfehlung

1 → 2 → 3 → 4 → 5 → 6 → 7 → 9 → 8 → 10 → 11 → 12. Shopify (9) kommt vor dem Metadaten-Schreiben (8), damit die Variant-ID beim einmaligen Schreiben schon vorliegt.
