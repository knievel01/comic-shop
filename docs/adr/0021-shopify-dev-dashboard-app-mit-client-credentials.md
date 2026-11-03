# ADR-0021: Shopify-Anbindung über eine Dev-Dashboard-App mit Client-Credentials

- **Status:** Akzeptiert
- **Datum:** 2026-11-03
- **Ergänzt:** ADR-0012 (Shopify-Datenmodell), ADR-0003 (Geheimnisse)

## Kontext
Shopify erlaubt seit dem 1. Januar 2026 keine neuen „benutzerdefinierten Apps“ im Shop-Admin mehr.
Neue Apps entstehen im Dev Dashboard (dev.shopify.com). Sie haben keinen festen Admin-Token, sondern
Client-ID und Client-Schlüssel; daraus holt der Dienst einen Zugriffstoken, der 24 Stunden gilt.
Bisher las der comic-helper einen festen `SHOPIFY_ADMIN_TOKEN` (docs/BETRIEB.md, `.env.example`).

Für den PoC steht kein Entwicklungsshop zur Verfügung. Auf ausdrückliche Entscheidung läuft der PoC
im vorhandenen Shop „Mein Shop“ (Plan Grow, mit Kundschaft und fremden Integrationen).

## Entscheidung
- App `comic-helper` im Dev Dashboard, Bereiche: `write_products`, `write_inventory`, `read_orders`,
  `read_locations`, `read_publications`. Installation im Shop über den Installationslink der App.
- Der comic-helper holt den Token selbst: `POST https://<shop>/admin/oauth/access_token` mit
  `grant_type=client_credentials`, Client-ID und Client-Schlüssel. Der Token wird je Prozess gecacht
  (Rand 5 min vor Ablauf) und bei HTTP 401 einmal neu geholt.
- Konfiguration: `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`. `SHOPIFY_ADMIN_TOKEN` bleibt als Weg für
  eine ältere benutzerdefinierte App bestehen; ist er gesetzt, wird er unverändert verwendet.
- Der Client-Schlüssel steht nur in `~/.config/comics/comics.env` (PoC) bzw. `/etc/comics/comics.env`,
  nie im Repo, nie im Chat (ADR-0003). Fehlermeldungen des Token-Aufrufs enthalten den Antworttext nicht.
- PoC-Schutz im echten Shop: `shopify.produkt_status: DRAFT` in `config/pricing.yaml`, `SHOPIFY_PUBLICATION_IDS`
  bleibt leer. Neue Produkte sind damit für Kundschaft unsichtbar.

## Konsequenzen
- Client-Credentials funktionieren nur, wenn App und Shop zur selben Shopify-Organisation gehören.
  Hier erfüllt, weil die App im Dev Dashboard desselben Kontos entstanden ist.
- Die App hat über `read_orders` Zugriff auf Bestellungen und damit Kundendaten (Shopify zeigt bei der
  Installation „Kund:innendaten“ und „Mitarbeiter:innen“). Der Bereich wird für den Verkaufs-Workflow 03
  gebraucht; wer ihn erst später will, nimmt ihn heraus und veröffentlicht eine neue App-Version.
- Webhook-Signaturen von Dev-Dashboard-Apps werden mit dem Client-Schlüssel erzeugt
  (`SHOPIFY_WEBHOOK_SECRET` = Client-Schlüssel).
- Nach dem PoC: Produktivbetrieb mit eigenem Shop oder bewusst im Hauptshop, dann `produkt_status` und
  Vertriebskanal neu entscheiden.

## Verworfene Alternativen
- Alte benutzerdefinierte App – nicht mehr anlegbar.
- Token von Hand aus dem Dev Dashboard kopieren – läuft nach 24 Stunden ab.
- Entwicklungsshop über ein Partner-Konto – wäre sauberer, wurde für den PoC abgewählt.

## Bezug
`comic_helper/shopify.py` (`access_token`), `comic_helper/config.py`, `.env.example`,
`config/pricing.yaml`, `docs/SHOPIFY-EINRICHTUNG.md`, ADR-0003, ADR-0012.
