# ADR-0006: Review-Oberfläche im comic-helper statt n8n-Formular

- **Status:** Akzeptiert
- **Datum:** 2026-10-27, konsolidiert 2026-11-13 (enthält frühere ADR-0020, ADR-0023; Löschen und Fortschritt: ADR-0004)

## Kontext
Die Prüfung braucht ein Formular mit Bildern, KI-Vorschlag, Zustand 0–4 mit Hilfetexten, Direktlinks und einem
live berechneten, überschreibbaren Endpreis. Offene Fälle müssen Neustarts überleben.

## Entscheidung
- Eigene Weboberfläche unter `/review/` im comic-helper. Zugriffsmodell: ADR-0025.
- Live-Preis per JavaScript; der Server rechnet beim Absenden verbindlich neu (`pricing.py`).
- Nach dem Bestätigen: Tag `status=bestaetigt`, Webhook an n8n; zusätzlich holt n8n alle 15 Minuten liegengebliebene
  Fälle (kein Verlust, wenn n8n gerade nicht läuft). Keine n8n-Wait-Nodes für den Review.
- **Zurückholen:** Ein bestätigtes Exemplar lässt sich auf `offen` zurückholen und ändern, **solange der Sidecar
  keinen Shopify-Eintrag hat**. Danach wird in Shopify korrigiert, nicht im Review (das Review greift nicht in den
  Shop ein).
- **Statistik-Seite** für KI-Kosten, Laufzeiten und gesparte Handarbeit. Kosten werden beim Anzeigen aus Token und
  Preisliste (`statistik.modellpreise_usd`) berechnet, nicht gespeichert; gesparte Zeit sind **Annahmen**
  (Minuten je Lauf), und Kosten und Einsparung werden nicht verrechnet.

## Konsequenzen
- Zustand liegt komplett in S3 (ADR-0004); Neustart oder Neuinstallation von n8n verliert nichts.
- Preisformel existiert zweimal (Python verbindlich, JS Vorschau) und muss synchron bleiben.
- Restrisiko beim Zurückholen: holt jemand zurück, während n8n gerade das Produkt anlegt, bleibt ein Exemplar mit
  `offen` und Shopify-Eintrag. Das Zeitfenster ist kurz; bei Bedarf später per Sperre im Sidecar schließen.
- Die Statistik liest bei jedem Aufruf alle Sidecars (ausreichend für heutige Mengen).

## Verworfene Alternativen
- n8n-Form/Wait-Node (kein Live-Preis, Fälle in Ausführungen versteckt).
- Bestätigte Exemplare direkt bearbeitbar lassen (n8n könnte mit altem Stand nach Shopify schreiben); Zurückholen
  auch nach Shopify (greift in den Shop ein).
- Kosten im Sidecar speichern (veralten bei Preisänderungen); n8n-REST-API für Laufzeiten (weiterer Schlüssel).

## Bezug
`comic_helper/app.py`, `statistik.py`, `templates/`
