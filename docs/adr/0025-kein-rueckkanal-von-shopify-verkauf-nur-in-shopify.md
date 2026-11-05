# ADR-0025: Kein Rückkanal von Shopify, Verkäufe werden nur in Shopify geführt

- **Status:** Akzeptiert
- **Datum:** 2026-11-05
- **Ersetzt:** ADR-0009, ADR-0016; in Teilen ADR-0004, ADR-0013, ADR-0021, ADR-0023 (siehe Konsequenzen)

## Kontext
Bisher meldete Shopify jede Bestellung, jedes Storno und jede Retoure per Webhook über einen
Cloudflare-Tunnel an den Comic-Rechner (ADR-0009, ADR-0016, Workflow 03). Daraufhin verschob der
comic-helper das Exemplar in S3 nach `verkauft/` und schrieb Verkaufsdatum und Bestellnummer an das Objekt.

Für den Go-Live (`docs/GO-LIVE.md`) hätte das ein Cloudflare-Konto, eine eigene Domain und den einzigen
Zugang aus dem Internet auf den Rechner gebraucht. Die Verkaufsdaten auf dem Rechner werden aber nicht
benötigt. Shopify führt Verkauf, Bezahlung, Storno, Retoure und Bestand vollständig selbst. Jedes
Exemplar ist eine Variante mit Bestand 1 (ADR-0012), Shopify setzt den Bestand beim Verkauf auf 0.
Ein Doppelverkauf ist damit auch ohne Rückkanal ausgeschlossen.

## Entscheidung
- Es gibt keinen Weg von Shopify oder aus dem Internet zum Comic-Rechner: kein Cloudflare-Tunnel,
  keine Shopify-Webhooks, kein Workflow 03. Der Rechner ruft Shopify nur selbst auf (Workflow 02).
- Verkäufe, Stornos und Retouren werden ausschließlich in Shopify geführt. S3 bildet sie nicht ab.
- Ein Exemplar bleibt nach dem Anlegen in Shopify dauerhaft in `aktiv/`, auch wenn es verkauft ist.
  Das Präfix `verkauft/` entfällt.
- Tagesmail und Statistik-Seite zeigen keine Verkäufe mehr (keine Zeile „Verkauft“, kein Workflow 03).
- Die Review-Übersicht zeigt in der ausgegrauten Gruppe nur noch die **letzten 30** in den Shop gestellten
  Exemplare, neueste zuerst. Die Gruppe heißt „Zuletzt in den Shop“, weil `aktiv/` auch Verkauftes enthält.

## Konsequenzen
- Leichter: kein Cloudflare-Konto, keine Domain, keine Webhook-Einrichtung in Shopify, kein öffentlicher
  Zugang zum Rechner. Die Firewall muss nur LAN-Zugriffe erlauben.
- Verloren: Auf dem Rechner ist nicht erkennbar, welche Exemplare verkauft sind. Für Auswertungen wie
  „Preise nach 100 Verkäufen nachjustieren“ (Plan, Phase 12) dient ein Bestellexport aus Shopify. Über die
  SKU (Kurz-ID, ADR-0013) lässt er sich mit den S3-Metadaten verbinden.
- `aktiv/` wächst mit jedem Exemplar weiter. Die Review liest davon nur die letzten 30 Einträge, die
  Tagesmail und die Statistik lesen das Präfix aber ganz (wie bisher).
- Folgen für bestehende ADRs:
  - ADR-0004: Präfix `verkauft/` entfällt, der Lebenszyklus endet in `aktiv/`.
  - ADR-0013: Die SKU behält die Kurz-ID. Sie dient jetzt der Zuordnung von Shopify-Exporten, nicht mehr
    einem Verkaufs-Webhook.
  - ADR-0021: `SHOPIFY_WEBHOOK_SECRET` entfällt.
  - ADR-0023: Die Statistik kennt nur noch Workflow 01 und 02.
- Im Repo entfernt: `comic_helper/webhooks.py`, `POST /api/shopify/webhook`, Workflow 03,
  `infra/k3s/optional/cloudflared/`, die Tunnel-Schritte in der Ansible-Rolle `apps`,
  `CLOUDFLARE_TUNNEL_TOKEN` und `SHOPIFY_WEBHOOK_SECRET` in `.env.example`.

## Verworfene Alternativen
- Webhooks über den Cloudflare-Tunnel beibehalten (ADR-0009/0016): Konto, Domain und öffentlicher Zugang
  für Daten, die nicht gebraucht werden.
- Bestellungen regelmäßig per Admin-API abfragen (nur ausgehend): erhält die Verkaufsdaten ohne Tunnel,
  ist aber zusätzlicher Code für Daten, die nicht gebraucht werden. Kann später als eigenes ADR kommen.

## Bezug
Plan 10 (entfällt), `docs/GO-LIVE.md`; `comic_helper/app.py`, `storage.py`, `report.py`, `statistik.py`,
`scripts/n8n-workflows-generieren.py`, `workflows/`, `os/ansible/roles/apps/`, `.env.example`.
