# Architektur

## Überblick

```
 Scanner ──NAPS2──> /srv/scans/neu/*.pdf
                         │  comics-scan-sync (systemd-Timer, 1 min)
                         │  prüft 2 Seiten, vergibt UUID, nur PutObject-Recht
                         ▼
 S3  eingang/<id>.pdf  (Tag status=neu)
                         │
 n8n 01 Scan-Ingest (alle 2 min) ──> comic-helper
                         │  claim -> PDF->JPEG -> Claude -> Vorschlag + Preisvorschlag
                         ▼
 S3  eingang/<id>.json, bilder/<id>-1|2.jpg, Tag status=offen, ki=sicher|nachkontrolle
                         │
 Fachkraft: https://comics-01/review/  (comic-helper, nur LAN)
                         │  Titel/Zustand/Z1-Preis bestätigen, Endpreis live
                         ▼
 Tag status=bestaetigt ──Webhook──> n8n 02 (+ 15-min-Nachzügler)
                         │  1. Shopify: Produkt/Variante anlegen (idempotent per SKU)
                         │  2. S3: Metadaten per CopyObject REPLACE, nach aktiv/
                         ▼
 S3  aktiv/<id>.pdf (alle Metadaten am Objekt)          Shopify: Variante, Menge 1
                                                            │ orders/paid
 Cloudflare-Tunnel (nur /webhook/*) ──> n8n 03 ──> comic-helper (HMAC)
                         ▼
 S3  verkauft/<id>.pdf       (orders/cancelled, refunds/create: zurück nach aktiv/)

 n8n 04 täglich 7:00 ──> comic-helper /api/report/daily ──> Mail
 n8n 99 Fehler-Alarm  <── errorWorkflow aller Workflows
```

Alles läuft auf einem Rechner (Ubuntu 24.04, K3s), Namespace `comics`:
`postgres` (nur n8n-intern), `n8n`, `comic-helper`, optional `cloudflared`.

## Zustände eines Exemplars

| Ort | Tag `status` | Bedeutung |
| --- | --- | --- |
| `eingang/` | `neu` | hochgeladen, noch nicht verarbeitet |
| `eingang/` | `in-arbeit` | von n8n übernommen (nach 30 min ohne Ergebnis wieder frei) |
| `eingang/` | `offen` | KI-Vorschlag liegt vor, wartet auf Fachkraft |
| `eingang/` | `fehler` | Erkennung fehlgeschlagen, im Review sichtbar („Erneut erkennen“) |
| `eingang/` | `bestaetigt` | Fachkraft hat bestätigt, Shopify/Metadaten stehen aus |
| `aktiv/` | `aktiv` | im Shop, Metadaten final |
| `verkauft/` | `verkauft` | verkauft |

Der Arbeitsstand (KI-Rohantwort, Entscheidung, Shopify-IDs) steht in `<prefix>/<id>.json`
neben der PDF. Er wird beim Verschieben mitgenommen.

## Entscheidungen

### E1 Ein Python-Dienst (`comic-helper`) statt Logik in n8n-Nodes

n8n orchestriert: Zeitpläne, Webhooks, Fehlerpfade, Mails, Alarm. Die Fachlogik (S3-Metadaten,
PDF-Rendering, Claude, Preisformel, Shopify-GraphQL, HMAC) liegt im `comic-helper`.

- Plan, Punkt 8/Offene Punkte 3: Die n8n-S3-Node kann keine benutzerdefinierten Metadaten per
  CopyObject REPLACE setzen. Ein HTTP-Dienst ist testbar und unabhängig von Sandbox-Grenzen.
- Alles hat Unit-Tests (`services/comic-helper/tests`, 35 Tests mit moto-S3, Fake-Claude, Fake-Shopify).
- Folge: Shopify-Token und Anthropic-Key liegen als Kubernetes-Secret beim Dienst, nicht als
  n8n-Credential. n8n braucht nur zwei Credentials (Helper-Token, SMTP).

### E2 Review-Oberfläche im comic-helper statt n8n-Formular mit Wait-Node

- n8n-Formulare können keinen live berechneten Endpreis anzeigen und Bilder nur eingeschränkt.
- Wait-Nodes überleben zwar Neustarts (Ausführungen liegen in Postgres), aber offene Fälle wären
  dann in n8n-Ausführungen versteckt. Hier ist der Status ein S3-Tag (Plan Phase 7, Ausweg).
  Ein Pod-Neustart oder sogar eine Neuinstallation von n8n verliert nichts.
- Die Oberfläche ist nur im LAN erreichbar (ufw), optional mit Passwort (`REVIEW_PASSWORD`).

### E3 SKU-Format

Plan: `asterix-xy-z3-a`. Umgesetzt: `asterix-12-z3-7f3a9c2b1234`, also Titel-Ausgabe-Zustand plus
die ersten 12 Hex-Stellen der Exemplar-UUID. Der Buchstabe (a, b, c) bleibt als Shopify-Option
„Exemplar“ erhalten. Grund: Der Verkaufs-Webhook findet das Bild direkt per S3-Präfix-Suche, ohne
40.000 Objekte durchsuchen zu müssen. Bei 12 Stellen liegt die Kollisionswahrscheinlichkeit bei
40.000 Exemplaren unter 1 zu 100.000, und Kollisionen werden erkannt.

### E4 Shopify-Datenmodell (Offene Punkte 2 und 6)

Ein Produkt je Titel + Ausgabe + Verlag. Optionen „Zustand“ („2 – gut“) und „Exemplar“ (a, b, …).
Shopify erlaubt 2.048 Varianten und 3 Optionen pro Produkt, das reicht auch für häufige Titel.
Der Verlag gehört in den Produktschlüssel, damit verschiedene Ausgaben (z. B. Nachdrucke anderer
Verlage) nicht in einem Produkt landen. **Vor dem Livegang mit Sepp klären** (Kommentar im
Architekturdokument): Ist ein Produkt mit Zustandsoption gewünscht oder ein Produkt je Zustand?
Umstellung wäre nur in `shopify.py` nötig (`product_handle`).

Verkaufte Varianten bleiben mit Bestand 0 stehen (Bestellhistorie, Storno). Im Theme
„ausverkaufte Varianten ausblenden“ aktivieren.

### E5 Preise

Zentrale Werte in `config/pricing.yaml` (Plan 6.3). n8n-Variablen sind in der Community-Edition
nicht verfügbar, deshalb eine Datei im Repo. Details: `docs/PREISFINDUNG.md`.

### E6 Erkennung: Claude, Ximilar optional

Claude (Modell per `CLAUDE_MODEL`, Standard `claude-opus-5-5`, Effort `low`) mit strukturierter
Ausgabe und Sicherheit je Feld. Gesamtsicherheit = Minimum aus Titel, Ausgabe und Verlag.
Bei Ablehnungen durch Sicherheitsfilter ist der serverseitige Fallback aktiv
(`fallbacks: "default"`). Eine Ximilar-Anbindung ist nicht gebaut. Sie wird nur ergänzt, wenn
der Vergleichstest (`scripts/vergleichstest.py`) das für US-Comics/Manga empfiehlt.
Ein automatischer Abgleich gegen eine Comic-Datenbank ist ebenfalls nicht gebaut: Comicguide
verbietet Data Mining, für GCD fehlt eine geprüfte Schnittstelle. Bis dahin gibt es Direktlinks im Formular.

### E7 ISO-Artefakt

Die ISO ist etwa 4 GB groß, GitHub-Release-Dateien dürfen höchstens 2 GiB haben. Die CI hängt
deshalb Teile an (`cat … > iso`). Alternative: lokal mit `os/build-iso.sh` bauen.

### E8 Öffentliche Erreichbarkeit

Nur `/webhook/*` von n8n ist über einen Cloudflare-Tunnel öffentlich (ausgehende Verbindung,
kein Port am Router). Editor und Review-Oberfläche sind nur im LAN erreichbar.
