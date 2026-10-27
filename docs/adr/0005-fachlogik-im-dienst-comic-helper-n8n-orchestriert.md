# ADR-0005: Fachlogik im Dienst comic-helper, n8n orchestriert

- **Status:** Akzeptiert
- **Datum:** 2026-10-27

## Kontext
Die n8n-S3-Node kann keine benutzerdefinierten Metadaten per CopyObject REPLACE setzen (Plan 8,
Offene Punkte 3). Logik in Code-Nodes ist schwer testbar und an Sandbox-Grenzen gebunden.

## Entscheidung
- Ein Python-Dienst (FastAPI) `comic-helper` im Cluster enthält: S3-Zugriff, PDF-Rendering, Claude-Erkennung,
  Preisformel, Shopify-GraphQL, Webhook-HMAC, Tagesbericht.
- n8n bleibt Orchestrierung: Zeitpläne, Webhook-Eingang, Fehlerpfade, Mail, Fehler-Alarm.
  n8n ruft den Dienst per HTTP mit Header `X-Helper-Token`.
- Jede Endpunkt-Operation ist idempotent (Wiederholung durch n8n ist ungefährlich).
- Fachlogik hat Unit-Tests (`services/comic-helper/tests`); neue Logik kommt mit Tests.

## Konsequenzen
- Shopify-Token und Anthropic-Key liegen beim Dienst (Kubernetes-Secret), nicht als n8n-Credential.
- n8n braucht nur die Credentials „Comic Helper Token“ und „SMTP Comics“.

## Verworfene Alternativen
- S3-Node plus Code-Nodes in n8n (Metadaten nicht machbar, schlecht testbar).

## Bezug
Plan 8; `services/comic-helper/`, `workflows/`
