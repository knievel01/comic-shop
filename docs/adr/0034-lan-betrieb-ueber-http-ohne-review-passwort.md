# ADR-0034: LAN-Betrieb über http, Review-Oberfläche ohne Passwort

- **Status:** Akzeptiert
- **Datum:** 2026-11-12

## Kontext
ADR-0006 nennt für die Review-Oberfläche ein HTTP-Basic-Passwort als optional; `docs/GO-LIVE.md` hatte es für den
Zielbetrieb als Pflicht notiert. Der Rechner hängt nur im Laden-LAN (ufw: 80/443 nur aus privaten Netzen, kein Tunnel,
ADR-0025). Das selbstsignierte Zertifikat erzeugt auf jedem Handy eine Warnung. Der Betreiber hat http ohne Anmeldung
ausdrücklich gewünscht (wie im PoC).

## Entscheidung
- Zugang per **http** auf Port 80 (Traefik-Entrypoint `web` ist bereits aktiv). `WEBHOOK_URL` und `REVIEW_BASE_URL`
  zeigen auf `http://<Rechnername>`. n8n bekommt `N8N_SECURE_COOKIE=false` (Editor-Login über http).
- `REVIEW_PASSWORD` bleibt leer, die Review-Oberfläche (`/review/`, Upload, Statistik) verlangt keine Anmeldung.
- n8n behält sein eigenes Owner-Konto (nicht abschaltbar); Port 443 bleibt für das LAN offen, wird aber nicht benutzt.

## Konsequenzen
- Wer im LAN ist (auch Gäste-WLAN, falls es im selben Netz liegt), kann Comics bestätigen, löschen und Preise ändern
  und Shopify-Entwürfe auslösen. Die Fritzbox sollte Gäste-WLAN vom LAN trennen.
- Passwörter und Links laufen unverschlüsselt im LAN; keine Eingabe sensibler Zugangsdaten in der Review-Oberfläche.
- Das Passwort lässt sich jederzeit wieder setzen (`REVIEW_PASSWORD` in `/etc/comics/comics.env`, dann
  `sudo comics-update --tags apps`).

## Verworfene Alternativen
- Passwort behalten – Betreiber wollte keine Anmeldung.
- Eigenes Zertifikat/ACME im LAN – zusätzlicher Aufwand, nicht gefordert.

## Bezug
ADR-0006, ADR-0008, ADR-0025; `infra/k3s/base/n8n.yaml`, `docs/GO-LIVE.md`
