# ADR-0009: Öffentlich nur /webhook/* über Cloudflare-Tunnel

- **Status:** Ersetzt durch ADR-0025
- **Datum:** 2026-10-27

## Kontext
Shopify muss Webhooks zustellen können. Editor und Review-Oberfläche dürfen nicht öffentlich sein.

## Entscheidung
- Ausgehender Cloudflare-Tunnel (`cloudflared` im Cluster), Public Hostname mit Pfadfilter `^/webhook/`.
- Kein offener Port am Router. Editor und Review nur im LAN (ufw).
- Shopify-Webhooks werden per HMAC geprüft (im comic-helper, Raw-Body von n8n weitergereicht).

## Konsequenzen
- Abhängigkeit von Cloudflare (kostenlos); ohne Tunnel-Token wird der Pod nicht ausgerollt.

## Verworfene Alternativen
- Portweiterleitung + Reverse Proxy (Angriffsfläche, dynamische IP).

## Bezug
Plan 3; `infra/k3s/optional/cloudflared/`, `docs/BETRIEB.md`
