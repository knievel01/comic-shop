# Machbarkeits-PoC auf vorhandenem K3s

> **Vorübergehende Testumgebung, keine neue Architekturentscheidung.** Der PoC weicht bewusst
> von mehreren akzeptierten ADRs ab, ersetzt aber keines davon. Deshalb gibt es dafür **kein ADR**.
> Das Zielbild bleibt der Comic-Rechner nach `docs/INSTALL.md`. Wird aus dem PoC ein Dauerbetrieb,
> braucht das vorher ein eigenes ADR (CLAUDE.md, Regel 2).

## Zweck

Prüfen, ob der Kern der Kette auf K3s zusammen funktioniert, bevor Hardware gekauft und die ISO
installiert wird: Postgres, n8n und `comic-helper` laufen, die Workflows lassen sich einspielen,
ein Scan in S3 wird erkannt und erscheint in der Review-Oberfläche.

Dafür wird der Stack aus `infra/k3s/` in das **bereits vorhandene, gemeinsam genutzte K3s** des
Entwickler-Rechners ausgerollt (K3s v1.34 mit Traefik und local-path, dort laufen auch andere
Namespaces wie `paperless`). Alles landet im Namespace `comics` und lässt sich mit einem Befehl
wieder entfernen.

Bestandteile:

- `infra/k3s-poc/kustomization.yaml`: Overlay über `infra/k3s`. Es **entfernt den Ingress**:
  Der gemeinsame Traefik ist aus dem ganzen LAN erreichbar, und anders als auf dem Comic-Rechner
  steht keine ufw davor (ADR-0008/0009). Ein n8n ohne Owner-Konto und eine Review-Oberfläche, die
  nach Shopify veröffentlichen kann, wären sonst für jeden im Netz offen. Außerdem bekommt der
  Namespace das Label `app.kubernetes.io/part-of=comics-poc`, und n8n wird für reines http auf
  localhost eingestellt (`N8N_SECURE_COOKIE=false`, `N8N_PROXY_HOPS=0`). `comic-helper` kommt aus
  der lokalen Registry `localhost:5000` und wird bei jedem Start neu gezogen (`imagePullPolicy: Always`).
- `infra/k3s-poc/registry.yaml`: Image-Registry (`registry:2.8.3`) mit Host-Netz, gebunden nur an
  `127.0.0.1:5000`, ohne Anmeldung, Images auf einem local-path-Volume (5 GiB). Damit gelangt das Image ohne `sudo` in K3s
  (`k3s ctr images import` bräuchte root); containerd zieht von `localhost` per http.
- `scripts/poc-host-k3s.sh`: Hilfsskript mit den Unterbefehlen `env`, `build`, `deploy`, `status`,
  `forward`, `forward-lan`, `delete`.

## Unterschiede zum Zielaufbau

| Thema | Zielaufbau (ADR) | PoC |
| --- | --- | --- |
| Rechner | eigener Comic-Rechner für Scan-Station und Server (ADR-0001) | vorhandener Entwickler-Rechner, K3s mit anderen Anwendungen geteilt |
| Installation | Autoinstall-ISO und `ansible-pull` (ADR-0002) | kein ISO, kein Ansible; manuell per `scripts/poc-host-k3s.sh` |
| Öffentliche Webhooks | nur `/webhook/*` über Cloudflare-Tunnel (ADR-0009) | **kein Tunnel**; Shopify-Webhooks kommen nicht an, nur lokale Tests per `curl` |
| Geheimnisse | `/etc/comics/comics.env`, Rechte 600, oder SOPS (ADR-0003) | `~/.config/comics/comics.env`, Rechte 600 (Benutzer statt root). Grundsatz von ADR-0003 gilt unverändert: nichts davon ins Repo |
| Zugriff | `https://comics-01/` im LAN über Traefik, ufw nur für LAN-Netze | kein Ingress; nur `kubectl port-forward` auf `127.0.0.1` (`http://localhost:5678/`, `:8080/review/`) |
| Scan und Upload | Scanner, `comics-scan-sync` mit UUID (ADR-0007) | kein Scanner, kein Sync-Timer; Fotos über `/review/hochladen` (ADR-0018) oder Test-PDF von Hand nach `eingang/` |
| Backup | `comics-backup.timer` (pg_dump, Workflow-Export nach S3) | kein Backup; PoC-Daten sind Wegwerfdaten |
| Image | per Ansible gebaut und importiert | per `docker build` gebaut, Push in die PoC-Registry `localhost:5000`, kein `sudo` |
| Preisquelle | Comicguide Z1 × Zustand × 1,5 (ADR-0011) | Booklooker-Angebot vorausgewählt, mit Pflicht-Beleg (Link), Aufschlag 1,0 (ADR-0017); vor dem Zielbetrieb `standard_preisquelle` zurücksetzen |

Unverändert gelten S3 als einziger Zustandsspeicher (ADR-0004), die Fachlogik im `comic-helper`
(ADR-0005), die Review-Oberfläche dort (ADR-0006) und n8n als Einzelinstanz mit Postgres (ADR-0008).

## Voraussetzungen

- `kubectl` mit Zugriff auf das lokale K3s über `~/.kube/config` (das Skript setzt `KUBECONFIG`
  standardmäßig darauf).
- `docker` (Benutzer in der Gruppe `docker`), `openssl`, `curl`. Port 5000 auf localhost frei.
- Ein S3-Bucket mit Zugangsschlüssel (`infra/aws/`, ADR-0004) und ein Anthropic-API-Key. Für den PoC
  empfiehlt sich ein eigener Test-Bucket bzw. -Präfix, nicht der spätere Produktiv-Bucket.
  Stand 01.11.2026: per AWS CLI nach `infra/aws/main.tf` und `iam.tf` angelegt (Bucket
  `comics-scans-roman-0001`, IAM-User `comics-app` und `comics-scan-upload`, eu-central-1).
  **Nicht im Terraform-State**; für den Betrieb per `terraform import` übernehmen oder neu anlegen.
- Optional ein Shopify-Entwicklungsshop (`docs/BETRIEB.md`, Abschnitt Shopify), sonst bleibt
  Workflow 02 ungetestet.

## Ablauf

Alle Befehle im Repo-Wurzelverzeichnis.

### 1. Geheimnisdatei anlegen

```bash
scripts/poc-host-k3s.sh env
```

Legt `~/.config/comics/comics.env` (Rechte 600) aus `.env.example` an, erzeugt
`N8N_ENCRYPTION_KEY`, `POSTGRES_PASSWORD`, `HELPER_TOKEN` und `REVIEW_PASSWORD` zufällig und setzt
`WEBHOOK_URL` auf `http://localhost:5678/` und `REVIEW_BASE_URL` auf `http://localhost:8080`.
Bricht ab, wenn die Datei schon existiert, damit der `N8N_ENCRYPTION_KEY` stabil bleibt.

Danach die Datei **im Editor** ergänzen, mindestens:
`S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `ANTHROPIC_API_KEY`;
optional die Shopify-Werte, **nur für einen Entwicklungsshop**. Format wie `.env.example`:
`NAME=wert`, keine Anführungszeichen; `deploy` bricht bei anderen Zeilen ab. Werte nicht in Terminal-Ausgaben, Chats oder
Tickets kopieren. Andere Pfade sind über `COMICS_ENV_FILE=…` möglich.

### 2. Image bauen und bereitstellen

```bash
scripts/poc-host-k3s.sh build
```

Startet die PoC-Registry, baut `localhost/comic-helper:local` mit Docker und pusht es als
`localhost:5000/comic-helper:local`. Kein `sudo` nötig, läuft auch innerhalb der Claude-App.
Nach jeder Codeänderung am `comic-helper`
wiederholen, danach Schritt 3.

### 3. Ausrollen

```bash
scripts/poc-host-k3s.sh deploy
```

Prüft Datei, Rechte und Format, warnt bei fehlenden S3-/Anthropic-Werten und gesetztem
Shopify-Shop, zeigt den kubectl-Kontext, wendet `infra/k3s-poc` an, legt das Secret `comics-env`
per Server-Side-Apply an (keine Kopie der Werte in der `last-applied`-Annotation) und wartet auf
Postgres, n8n und `comic-helper`. Bei einem erneuten Lauf werden `comic-helper` und n8n neu
gestartet (neues Image, geänderte Secrets). Fehlt das Image, bricht es nach 3 Minuten mit Hinweis ab.

### 4. Status prüfen und verbinden

```bash
scripts/poc-host-k3s.sh status
scripts/poc-host-k3s.sh forward      # läuft, bis Strg-C
```

## Zugriff

Standardmäßig nur über `forward` (Port-Forward auf `127.0.0.1`, aus dem LAN nicht erreichbar):

- **n8n:** <http://localhost:5678/>. **Gleich nach dem ersten Deploy** das Owner-Konto anlegen
  (nur für den PoC, nicht das spätere Produktivkonto).
- **Review-Oberfläche:** <http://localhost:8080/review/>, HTTP Basic mit beliebigem Benutzernamen
  und `REVIEW_PASSWORD` aus der Geheimnisdatei.
- Andere Ports: `N8N_PORT=… HELPER_PORT=… scripts/poc-host-k3s.sh forward` (dann vorher
  `WEBHOOK_URL`/`REVIEW_BASE_URL` in der Datei anpassen und `deploy`).
- Logs: `kubectl -n comics logs deploy/comic-helper` bzw. `deploy/n8n`.

### Vom Handy im WLAN

`scripts/poc-host-k3s.sh forward-lan` lauscht zusätzlich auf der LAN-IP des Rechners
(automatisch ermittelt, sonst `LAN_IP=…`) und zeigt die Adressen an, z. B.
`http://192.168.40.123:5678/` und `http://192.168.40.123:8080/review/`.

- Nur unverschlüsseltes http: Review-Passwort und n8n-Anmeldung gehen im Klartext durchs WLAN,
  und jedes Gerät im Netz kann die Seiten aufrufen. Nur im eigenen, vertrauten WLAN verwenden
  und nach dem Test mit Strg-C beenden.
- Startet nur, wenn n8n schon ein Owner-Konto hat (sonst würde der erste Besucher Owner).
- Ist ufw aktiv, die Ports einmalig für das LAN freigeben (braucht root, selbst ausführen):
  `sudo ufw allow from 192.168.40.0/24 to any port 5678,8080 proto tcp`.
  Nach dem PoC wieder entfernen: `sudo ufw delete allow from 192.168.40.0/24 to any port 5678,8080 proto tcp`.
- Links in n8n-Mails und Webhook-Adressen zeigen weiter auf `localhost`.

## Workflows einspielen

Es gilt der Ablauf aus `docs/BETRIEB.md`, Abschnitt „3. n8n“, mit folgenden Anpassungen:

1. In n8n die Credentials mit **genau diesen Namen** anlegen:
   - „Comic Helper Token“: Typ *Header Auth*, Name `X-Helper-Token`, Wert = `HELPER_TOKEN` aus
     `~/.config/comics/comics.env`.
   - „SMTP Comics“: Typ *SMTP*; nur nötig, wenn Tagesmail und Fehler-Alarm getestet werden.
2. Workflows importieren, **ohne `sudo`** und mit der Benutzer-Kubeconfig (das Skript nimmt sonst
   `/etc/rancher/k3s/k3s.yaml`, das nur für root lesbar ist):

   ```bash
   KUBECONFIG=~/.kube/config scripts/n8n-import.sh
   ```

3. Credentials in den Workflows zuordnen, falls n8n das nicht automatisch tut, dann aktivieren.
   Sinnvoll im PoC: **01** (Scan-Ingest und Erkennung, Polling alle 2 Minuten) und **02**
   (Bestätigt → Shopify, nur mit Entwicklungsshop). **03** (Shopify-Verkauf) bekommt ohne Tunnel
   keine echten Webhooks, lässt sich aber lokal mit `curl` gegen
   `http://localhost:5678/webhook/shopify-orders` (bei laufendem `forward`) anstoßen (Signatur nötig, siehe
   `SHOPIFY_WEBHOOK_SECRET`). **04** und **99** nur mit SMTP-Credential.
4. Der Schritt „exportieren und committen“ aus `docs/BETRIEB.md` entfällt im Normalfall. Nur wenn
   im PoC bewusst eine Workflow-Änderung entstanden ist, die ins Repo soll:
   `KUBECONFIG=~/.kube/config scripts/n8n-export.sh`, dann `git diff workflows/` prüfen und wie
   gewohnt committen (Export ohne Credentials, niemals `--decrypted`).

## Erster Test

Am einfachsten über die Review-Oberfläche: **Hochladen** (`/review/hochladen`), ein Foto vom Cover
und eins von der Rückseite wählen (auf dem Handy aus Kamera oder Galerie). Der comic-helper legt
daraus die zweiseitige PDF unter `eingang/{UUID}.pdf` mit `status=neu` ab (ADR-0018).

Alternativ wird eine zweiseitige Test-PDF von Hand so abgelegt, wie es
`comics-scan-sync` tun würde (ADR-0007: Name `{UUID}.pdf`, Tag `status=neu`):

```bash
aws s3api put-object --bucket <S3_BUCKET> --key "eingang/$(uuidgen).pdf" \
  --body test.pdf --tagging status=neu
```

Zugangsdaten dafür über ein eigenes AWS-Profil oder Umgebungsvariablen in der eigenen Shell,
nicht auf der Kommandozeile. Innerhalb von etwa 3 Minuten steht das Exemplar unter
`http://localhost:8080/review/` und hat in S3 den Tag `status=offen`.

## Aufräumen

```bash
scripts/poc-host-k3s.sh delete
```

Löscht nach Eingabe von `loeschen` den Namespace `comics` samt PVCs (n8n-Datenbank weg), aber nur,
wenn er das PoC-Label trägt. Andere Namespaces des K3s bleiben unberührt. Bewusst **nicht** gelöscht werden:

- `~/.config/comics/comics.env`: bei Bedarf selbst löschen (`rm ~/.config/comics/comics.env`).
  Darin stehende echte Schlüssel (AWS, Anthropic, Shopify) nach dem PoC gegebenenfalls widerrufen.
- das lokale Image in Docker: `docker image rm localhost/comic-helper:local localhost:5000/comic-helper:local`.
  Die Registry selbst verschwindet mit dem Namespace.
- Testdaten im S3-Bucket (`eingang/`, `aktiv/`, `verkauft/`) und Testprodukte im Shopify-Entwicklungsshop.
