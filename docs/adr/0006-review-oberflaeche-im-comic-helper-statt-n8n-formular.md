# ADR-0006: Review-Oberfläche im comic-helper statt n8n-Formular

- **Status:** Akzeptiert
- **Datum:** 2026-10-27

## Kontext
Plan 7 verlangt ein Formular mit Bildern, KI-Vorschlag, Zustand 0–4 mit Hilfetexten, Direktlinks und
einem live berechneten, überschreibbaren Endpreis. Offene Fälle müssen Neustarts überleben.

## Entscheidung
- Eigene Weboberfläche unter `/review/` im comic-helper (nur LAN, optional HTTP-Basic-Passwort).
- Live-Preis per JavaScript; der Server rechnet beim Absenden verbindlich neu (`pricing.py`).
- Nach dem Bestätigen: Tag `status=bestaetigt`, Webhook an n8n; zusätzlich holt n8n alle 15 Minuten
  liegengebliebene Fälle (kein Verlust, wenn n8n gerade nicht läuft).
- Keine n8n-Wait-Nodes für den Review.

## Konsequenzen
- Zustand liegt komplett in S3 (ADR-0004); Neustart oder Neuinstallation von n8n verliert nichts.
- Preisformel existiert zweimal (Python verbindlich, JS Vorschau) und muss synchron bleiben.

## Verworfene Alternativen
- n8n-Form/Wait-Node (kein Live-Preis, Fälle in Ausführungen versteckt).

## Bezug
Plan 7; `comic_helper/app.py`, `templates/review.html`
