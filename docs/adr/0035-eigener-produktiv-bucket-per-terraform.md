# ADR-0035: Eigener Produktiv-Bucket per Terraform, IAM-Namen mit Präfix

- **Status:** Akzeptiert
- **Datum:** 2026-11-12
- **Ersetzt:** ADR-0033

## Kontext
ADR-0033 ließ den Go-Live vorläufig mit dem PoC-Bucket laufen, weil Terraform und die AWS-Anmeldung fehlten. GO-LIVE E5
sieht einen eigenen Produktiv-Bucket vor, ADR-0027 verlangt getrennte Daten von Sandbox und Zielbetrieb. Die IAM-User
`comics-app` und `comics-scan-upload` belegt der PoC im selben AWS-Konto, IAM-Namen sind pro Konto eindeutig.

## Entscheidung
- `infra/aws` legt den Bucket `comics-scans-roman-prod-0001` an (`eu-central-1`), dazu die IAM-User
  `comics-prod-app` und `comics-prod-scan-upload`. Neue Variable `name_prefix` (Standard `comics`) steuert die IAM-Namen.
- Der Comic-Rechner nutzt ausschließlich diese Zugangsdaten (`/etc/comics/comics.env`). Der PoC-Bucket und seine
  Schlüssel bleiben der Sandbox.
- Terraform-State (enthält die Schlüssel) bleibt lokal in `infra/aws`, nicht im Git (Rechte 600).

## Konsequenzen
- Produktion startet mit leeren Daten und leerer Statistik; Sandbox und Produktion verarbeiten nie dieselben Scans.
- Shopify-App und Anthropic-Konto sind weiterhin gemeinsam (vorläufig); bei Aktivierung beider Systeme schreiben beide
  Entwürfe in denselben Shop. Ablösung durch eigenen Dev-Shop für die Sandbox steht aus.
- Der State muss gesichert werden (Passwort-Manager); ohne ihn lassen sich Schlüssel nicht neu auslesen.

## Verworfene Alternativen
- Weiter mit dem PoC-Bucket – vermischt Testdaten und Produktion (ADR-0033, jetzt abgelöst).
- IAM-Namen des PoC übernehmen – kollidiert mit bestehenden Usern.

## Bezug
GO-LIVE E5, ADR-0003, ADR-0027, ADR-0033; `infra/aws`
