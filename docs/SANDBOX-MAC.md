# Sandbox auf dem MacBook mit OrbStack

Gemäß ADR-0039 (ersetzt ADR-0038): Die Sandbox läuft als **Docker Compose in OrbStack**, ohne K3s.
Alles dafür liegt im Repo: `infra/sandbox-orbstack/compose.yaml` und `scripts/sandbox-orbstack.sh`.
Jede Änderung an comic-helper, Workflows und `config/pricing.yaml` kommt zuerst hierher (ADR-0027),
danach auf den Comic-Rechner. Die Sandbox nutzt nie Produktivdaten.

## Ziel

Postgres, n8n und comic-helper laufen lokal. Ein Foto im Hochladen-Formular wird erkannt, erscheint in der
Review-Oberfläche und lässt sich in den Shopify-Entwicklungsshop übernehmen.

- n8n: <http://localhost:5678/>
- Review-Oberfläche: <http://localhost:8080/review/>

Beide Ports sind nur an `127.0.0.1` gebunden, im WLAN ist nichts erreichbar.

## Stand

Im Repo fertig, **unter Linux mit Docker 29 getestet**: Compose-Datei, Skript, Start bis „healthy“ aller drei
Container, Netzwerk-Alias für die Workflows, Import der vier Workflows in n8n.

**Auf dem Mac mit OrbStack noch nicht ausprobiert.** Nicht getestet ist auch ein kompletter Durchlauf mit echtem
Bucket, Anthropic-Key und Shopify-Entwicklungsshop. Ohne `S3_BUCKET` antwortet die Review-Seite mit 500.

## Schritte

### 1. OrbStack installieren
- `brew install --cask orbstack`, OrbStack einmal starten. Die Docker-CLI mit Compose kommt mit.
- Prüfung: `docker compose version` und `docker info` laufen ohne Fehler.

### 2. Geheimnisdatei anlegen
```bash
scripts/sandbox-orbstack.sh env
```
Legt `~/.config/comics/comics.env` (Rechte 600) aus `.env.example` an und erzeugt `N8N_ENCRYPTION_KEY`,
`POSTGRES_PASSWORD` und `HELPER_TOKEN` zufällig. `WEBHOOK_URL` und `REVIEW_BASE_URL` zeigen auf `localhost`.
Danach im Editor mindestens `S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` und `ANTHROPIC_API_KEY` eintragen.
Shopify nur mit Entwicklungsshop. Format `NAME=wert`, keine Anführungszeichen. Werte nicht in Chats oder Tickets kopieren.
Der Test-Bucket ist ein eigener, nicht der Produktiv-Bucket (ADR-0035).

### 3. Starten
```bash
scripts/sandbox-orbstack.sh up
```
Baut das comic-helper-Image und startet alles. Bei einer Codeänderung dasselbe Kommando noch einmal: Compose baut neu und
ersetzt nur den geänderten Container.
- Prüfung: `scripts/sandbox-orbstack.sh status` zeigt drei Container `healthy`.

### 4. n8n einrichten
1. <http://localhost:5678/> öffnen und gleich das Owner-Konto anlegen (nur für die Sandbox).
2. Credentials mit **genau diesen Namen** anlegen: „Comic Helper Token“ (*Header Auth*, Name `X-Helper-Token`, Wert =
   `HELPER_TOKEN` aus der Geheimnisdatei) und, nur für Tagesmail und Fehler-Alarm, „SMTP Comics“.
3. Workflows importieren:
   ```bash
   scripts/sandbox-orbstack.sh import
   ```
4. Credentials zuordnen und Workflows aktivieren. Sinnvoll: **01** (Scan-Ingest und Erkennung) und **02**
   (Bestätigt → Shopify, nur mit Entwicklungsshop); **04** und **99** nur mit SMTP. Aktiv-Zustand liegt in der
   n8n-Datenbank, nicht im Repo (dort bleibt `active: false`). Aktivieren per CLI statt Oberfläche, falls gewünscht:
   ```bash
   docker compose --env-file ~/.config/comics/comics.env -f infra/sandbox-orbstack/compose.yaml \
     exec -T n8n n8n update:workflow --id=<ID> --active=true
   ```
   Danach n8n neu starten, sonst greift die Aktivierung nicht (`docker compose … restart n8n`).
   Workflow-IDs: `… exec -T n8n n8n list:workflow`.
5. Ändert die Sandbox bewusst einen Workflow, der ins Repo soll: in n8n exportieren und committen wie in
   `docs/BETRIEB.md` (ohne Credentials, niemals `--decrypted`).

Die Workflows rufen `http://comic-helper.comics.svc.cluster.local:8080` auf. Der Compose-Container trägt diesen Namen
als Alias, es ist nichts an den Workflows zu ändern.

### 5. Erster Test
In der Review-Oberfläche **Hochladen**, ein Foto vom Cover und eins von der Rückseite wählen. Der comic-helper legt die
zweiseitige PDF unter `eingang/{UUID}.pdf` mit `status=neu` ab (ADR-0018). Workflow 01 holt sie innerhalb weniger
Minuten ab; danach steht das Exemplar unter „Zu prüfen“.

### 6. Täglicher Betrieb
| Aufgabe | Befehl |
| --- | --- |
| Logs | `scripts/sandbox-orbstack.sh logs [comic-helper\|n8n\|postgres]` |
| Stoppen, Daten behalten | `scripts/sandbox-orbstack.sh down` |
| Alles löschen (n8n-Datenbank weg) | `scripts/sandbox-orbstack.sh reset` |

`restart: unless-stopped` startet die Container nach einem Neustart von OrbStack wieder. OrbStack selbst lässt sich in
dessen Einstellungen beim Login starten. Schläft der Mac, stehen die Container still; laufende Tests also wach halten
(`caffeinate -i`).

### 7. Vom Handy erreichen (optional, nicht Teil von ADR-0039)
Die Ports sind absichtlich nur lokal. Wer die Sandbox unterwegs braucht, installiert Tailscale auf dem Mac und
veröffentlicht den Port im Tailnet mit `tailscale serve`; die genaue Syntax ist **nicht geprüft**, bitte vor Gebrauch
`tailscale serve --help` lesen. Ports auf `0.0.0.0` zu öffnen ist keine Lösung: Ohne `REVIEW_PASSWORD` könnte dann jedes
Gerät im Netz Comics bestätigen und hochladen.

## Was die Sandbox nicht prüft

Kubernetes-Besonderheiten aus `infra/k3s`: Ingress-Pfade, `securityContext`, Probes, Secret-Einbindung, Volumes. Änderungen an
`infra/k3s/` und `os/` werden gerendert (`kubectl kustomize infra/k3s`) und beim ersten Rollout bewusst auf dem
Comic-Rechner beobachtet (ADR-0039). Außerdem: `arm64` hier gegen `amd64` auf dem Comic-Rechner.

Die Image-Versionen von Postgres und n8n stehen in `infra/k3s/base/` **und** in `infra/sandbox-orbstack/compose.yaml`.
Wer eine ändert, ändert beide.

## Abnahme

- [ ] `scripts/sandbox-orbstack.sh up` läuft auf dem Mac durch, alle drei Container sind `healthy`.
- [ ] Ein Foto läuft über **Hochladen** bis zur Bestätigung, mit Test-Bucket und Entwicklungsshop.
- [ ] Nach einem Neustart von OrbStack sind die Container wieder oben.
- [ ] `~/.config/comics/comics.env` hat Rechte 600, nichts davon steht im Repo.

## Risiken

- **Schlafmodus:** Die Sandbox ist aus, sobald der Mac schläft.
- **Unterschied zum Zielaufbau:** siehe oben; Fehler, die nur in Kubernetes auftreten, fallen erst auf dem Comic-Rechner auf.
- **Apple-Silicon-spezifisch:** Alle verwendeten Images (Postgres, n8n, python-slim) haben `arm64`-Varianten; ein neues Paket im
  `comic-helper` könnte das ändern.
