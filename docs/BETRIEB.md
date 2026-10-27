# Betrieb

## Ersteinrichtung nach `INSTALL.md`

### 1. Shopify

1. Admin → Einstellungen → Apps → App-Entwicklung → **Custom App** „Comic-Automatisierung“.
   Admin-API-Scopes: `read_products`, `write_products`, `read_inventory`, `write_inventory`,
   `read_orders`, `read_publications`, `write_publications`.
   Token → `SHOPIFY_ADMIN_TOKEN`, Shop-Domain (`xyz.myshopify.com`) → `SHOPIFY_SHOP_DOMAIN`.
2. Standort-ID (Einstellungen → Standorte, Zahl in der URL) → `SHOPIFY_LOCATION_ID`.
3. Publication-ID des Online Stores (GraphQL `publications { nodes { id name } }`) → `SHOPIFY_PUBLICATION_IDS`.
4. Webhooks (Einstellungen → Benachrichtigungen → Webhooks, Format JSON, aktuelle API-Version), jeweils an
   `https://hooks.<domain>/webhook/shopify-orders`:
   `Bestellung bezahlt` (orders/paid), `Bestellstornierung` (orders/cancelled), `Rückerstattung erstellt` (refunds/create).
   Das dort angezeigte Signatur-Secret → `SHOPIFY_WEBHOOK_SECRET`.
   (Bei Webhooks einer Custom App ist das Secret der API-Secret-Key der App.)
5. Theme: ausverkaufte Varianten ausblenden.
6. Zuerst mit einem **Entwicklungs-/Testshop** und `produkt_status: DRAFT` in `config/pricing.yaml` beginnen.

### 2. Cloudflare-Tunnel (öffentliche Webhooks)

Zero Trust → Networks → Tunnels → „comics“ anlegen, Token → `CLOUDFLARE_TUNNEL_TOKEN`.
Public Hostname: `hooks.<domain>`, **Path `^/webhook/`**, Service `http://n8n.comics.svc.cluster.local:5678`.
`WEBHOOK_URL=https://hooks.<domain>/`. Nach `sudo comics-update` läuft der Pod `cloudflared`.
Test: `curl https://hooks.<domain>/` liefert 404, `curl https://hooks.<domain>/webhook/…` erreicht n8n.

### 3. n8n

1. `https://comics-01/` im LAN öffnen, Owner-Konto anlegen (Zugang in den Passwort-Manager).
2. Credentials anlegen, **Namen genau so**:
   - „Comic Helper Token“: Typ *Header Auth*, Name `X-Helper-Token`, Wert = `HELPER_TOKEN`.
   - „SMTP Comics“: Typ *SMTP*, Werte aus dem Passwort-Manager.
3. Workflows einspielen: `sudo /opt/comic-shop/scripts/n8n-import.sh`.
4. In jedem Workflow die beiden Credentials auswählen, falls n8n sie nicht automatisch zuordnet,
   dann alle Workflows aktivieren. „Comics 99 Fehler-Alarm“ ist bereits als Error-Workflow eingetragen.
5. `sudo /opt/comic-shop/scripts/n8n-export.sh` und den Export committen.

### 4. Erste Prüfung

Eine Test-PDF mit zwei Seiten nach `/srv/scans/neu/` legen. Innerhalb von 3 Minuten:
`eingang/<id>.pdf` in S3 hat den Tag `status=offen`, das Exemplar steht unter `https://comics-01/review/`.

## Tagesgeschäft

Siehe `docs/SCANNEN-UND-BESTAETIGEN.md`.

## Workflows ändern

In der n8n-UI ändern, dann **sofort** exportieren und committen:

```bash
sudo /opt/comic-shop/scripts/n8n-export.sh
cd /opt/comic-shop && git diff --stat workflows/ && git commit -am "n8n: <was>" && git push
```

Der Export enthält keine Credentials (kein `--decrypted`).

## Konfiguration ändern (Preise, Versionen)

Datei im Repo ändern → commit/push → auf dem Rechner `sudo comics-update` (oder `--tags apps`).
Der comic-helper wird dabei neu gebaut (`podman`) und neu gestartet.

## Monitoring

- Workflow-Fehler → Mail an `MAIL_TO_ALERTS` (Workflow „Comics 99 Fehler-Alarm“).
- Tagesmail um 7 Uhr: steigen „Fehler“ oder „Bestätigt, noch nicht im Shop“, nachsehen.
- `kubectl -n comics get pods`, `kubectl -n comics logs deploy/comic-helper`.
- Rechner: `sudo /opt/comic-shop/scripts/verify.sh --skip-scan`.

## Backup und Wiederherstellung

Täglich 02:30 (`comics-backup.timer`): `pg_dump` der n8n-Datenbank und Workflow-Export nach
`s3://<bucket>/backup/<datum>/` (90 Tage). Zusätzlich liegen die Workflows im Repo.
Die Comic-Daten selbst liegen versioniert in S3 (Versionen 30 Tage).

**`N8N_ENCRYPTION_KEY` und `comics.env` stehen im Passwort-Manager.** Ohne den Key sind die
n8n-Credentials nach einer Wiederherstellung unbrauchbar (dann neu anlegen, siehe oben).

Wiederherstellung auf frischem K3s (Abnahme Phase 12):

```bash
sudo comics-update                                   # Apps laufen, n8n-DB leer
aws s3 cp s3://<bucket>/backup/<datum>/n8n.dump /tmp/n8n.dump
kubectl -n comics scale deploy/n8n --replicas=0
kubectl -n comics exec -i statefulset/postgres -- sh -c 'pg_restore -U n8n -d n8n --clean --if-exists' < /tmp/n8n.dump
kubectl -n comics scale deploy/n8n --replicas=1
# Alternative ohne Dump: scripts/n8n-import.sh (Workflows aus dem Repo) + Credentials neu anlegen
```

Danach prüfen: Workflows vorhanden und aktiv, `verify.sh` grün.

## Kosten

| Posten | Größenordnung | Kontrolle |
| --- | --- | --- |
| Claude-API | 2–72 $/Monat bei 2.000 Scans, je nach Modell (siehe PREISFINDUNG.md) | Anthropic Console → Usage; Token je Scan in `eingang/<id>.json` (`ki_info`) |
| S3 | 40.000 PDFs à ~5 MB + Bilder ≈ 300 GB → ca. 7 $/Monat Standard; Requests vernachlässigbar | AWS Cost Explorer, Tag `project=comic-shop` |
| Transfer | Shopify lädt Bilder einmal; gering | |
| Cloudflare-Tunnel | kostenlos | |

Speicherkosten senken: alte `verkauft/`-PDFs per Lifecycle nach Glacier Instant Retrieval (in
`infra/aws/main.tf` ergänzen, wenn gewünscht).

## End-to-End-Test vor dem Livegang (Phase 12)

1. 50 echte Comics scannen und bestätigen (mindestens 1 mit Korrektur, 1 mit überschriebenem Preis).
2. Zwischen Scan und Bestätigung `kubectl -n comics rollout restart deploy/n8n deploy/comic-helper`. Nichts geht verloren.
3. Im Testshop: Variante mit SKU, Preis, Bestand 1 und Bild prüfen.
4. Testbestellung → PDF liegt in `verkauft/`. Webhook in Shopify erneut senden → keine Änderung.
5. Bestellung stornieren → PDF wieder in `aktiv/`.
6. Tagesmail am nächsten Morgen mit S3-Stand vergleichen.
7. `aws s3api head-object --bucket <bucket> --key aktiv/<id>.pdf` zeigt alle Metadaten.
