# ADR-0033: Go-Live startet vorläufig mit PoC-Bucket und PoC-Shopify-App

- **Status:** Ersetzt durch ADR-0035
- **Datum:** 2026-11-12

## Kontext
GO-LIVE E5 sieht einen neuen Produktiv-Bucket per Terraform vor, ADR-0027 verlangt, dass Sandbox und Zielbetrieb weder
Bucket noch Datenbank teilen. Beim Go-Live auf dem Laptop war die AWS-Anmeldung auf dem Entwicklungsrechner abgelaufen
und Terraform nicht installiert. Die Zugangsdaten (S3/IAM, Anthropic, Shopify-App) lagen nur in der Sandbox
(`~/.config/comics/comics.env` auf pro-mini). Die Entscheidung kam vom Betreiber ausdrücklich ("Nimm den selben Bucket").

## Entscheidung
- Das Laptop nutzt vorläufig denselben S3-Bucket, dieselben IAM-Schlüssel, dieselbe Shopify-App und dasselbe
  Anthropic-Konto wie die Sandbox. Intern werden neue Werte erzeugt: `N8N_ENCRYPTION_KEY`, `POSTGRES_PASSWORD`,
  `HELPER_TOKEN`, `REVIEW_PASSWORD`. Die Adressen zeigen auf das Laptop.
- **Vor dem Aktivieren von Workflow 01/02 auf dem Laptop** müssen die Workflows 01/02 der Sandbox deaktiviert sein,
  sonst holen beide Systeme jeden Scan ab (doppelte Claude-Kosten, doppelte Shopify-Entwürfe).
- Ablösung: Produktiv-Bucket per `infra/aws` anlegen (E5), Zugangsdaten in `/etc/comics/comics.env` tauschen,
  Sandbox auf eigenen Bucket/Dev-Shop umstellen (GO-LIVE "PoC wird Sandbox"). Dann Status `Ersetzt durch` oder
  Hinweis auf die Umsetzung.

## Konsequenzen
- Sandbox und Produktion sind bis zur Ablösung nicht getrennt; die Sandbox ist keine Rückfallebene für die Verarbeitung.
- Statistik und Testdaten des PoC liegen im selben Bucket (E5 wollte einen leeren).
- Die Geheimnisse bleiben außerhalb des Repos (ADR-0003).

## Verworfene Alternativen
- Neuer Bucket sofort – Terraform und AWS-Anmeldung waren nicht verfügbar.
- Sandbox-Workflows sofort pausieren – vom Betreiber nicht verlangt; Aktivierung auf dem Laptop ist noch offen.

## Bezug
GO-LIVE E5, ADR-0003, ADR-0027, ADR-0028; `docs/GO-LIVE.md`
