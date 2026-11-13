# ADR-0025: Kein Zugang aus dem Internet, Zugriff nur im LAN, Verkäufe nur in Shopify

- **Status:** Akzeptiert
- **Datum:** 2026-11-05, konsolidiert 2026-11-13 (enthält frühere ADR-0009, ADR-0016, ADR-0034, ADR-0036, ADR-0037)

## Kontext
Ursprünglich meldete Shopify jede Bestellung per Webhook über einen Cloudflare-Tunnel an den Rechner, der das
Exemplar nach `verkauft/` verschob. Das hätte ein Cloudflare-Konto, eine Domain und den einzigen Zugang aus dem Internet
gebraucht, für Daten, die der Rechner nicht braucht: Shopify führt Verkauf, Zahlung, Storno, Retoure und Bestand selbst,
und jede Variante hat Bestand 1, ein Doppelverkauf ist ausgeschlossen. Der Rechner steht im Laden-LAN; der Betreiber
wollte keine Anmeldung und kein Zertifikat-Theater.

## Entscheidung
- **Kein Weg aus dem Internet zum Rechner:** kein Tunnel, keine Shopify-Webhooks, kein Workflow 03. Der Rechner ruft
  Shopify nur selbst auf. Firewall (ufw): 80/443 und SSH nur aus privaten Netzen.
- **Verkäufe, Stornos, Retouren gibt es nur in Shopify.** S3 bildet sie nicht ab; ein Exemplar bleibt dauerhaft in
  `aktiv/`. Die Review zeigt „Zuletzt in den Shop“ (letzte 30); Tagesmail und Statistik kennen keine Verkäufe.
- **LAN-Zugang per http, ohne Anmeldung:** Review-Oberfläche (`/review/`, Upload, Statistik) ohne Passwort
  (`REVIEW_PASSWORD` leer, kann gesetzt werden); n8n mit `N8N_SECURE_COOKIE=false` und eigenem Owner-Konto.
- **Der Benutzer `scan` (Autologin) bekommt die Cluster-Admin-Kubeconfig** wie `comicadmin`.

## Konsequenzen
- Leichter: kein Cloudflare-Konto, keine Domain, keine Webhook-Einrichtung; die Angriffsfläche ist das LAN.
- Verloren: Auf dem Rechner ist nicht erkennbar, was verkauft ist. Auswertungen (z. B. Preise nach 100 Verkäufen)
  laufen über einen Shopify-Bestellexport, verbunden über die Kurz-ID in der SKU (ADR-0012). `aktiv/` wächst weiter.
- **Wer im LAN ist (auch Gäste-WLAN im selben Netz), kann Comics bestätigen, löschen, Preise ändern und
  Shopify-Entwürfe auslösen.** Die Fritzbox sollte Gäste-WLAN trennen. Verkehr ist unverschlüsselt: keine sensiblen
  Zugangsdaten in der Oberfläche.
- **Vertrauensanker ist die physische Anmeldung am Laptop:** `scan` hat kein sudo, kann mit Cluster-Admin aber Pods mit
  Host-Zugriff starten und so Root erlangen und alle Secrets lesen.
- Passwort und eingeschränktes `kubectl` lassen sich später wieder einführen (Namespace-begrenzt per RoleBinding auf
  `admin`, Details in der Git-Historie).

## Verworfene Alternativen
- Webhooks über Cloudflare-Tunnel; Bestellungen per Admin-API abfragen (ausgehend, aber Code für ungenutzte Daten;
  kann als eigenes ADR kommen).
- Passwort behalten, selbstsigniertes Zertifikat oder ACME im LAN (Warnung auf jedem Handy bzw. Zusatzaufwand).
- `kubectl` für `scan` nur im Namespace `comics` (vom Betreiber nicht gewünscht).

## Bezug
`docs/GO-LIVE.md`, `infra/k3s/base/` (`ingress.yaml`, `n8n.yaml`), `os/ansible/roles/k3s`, `comic_helper/app.py`
