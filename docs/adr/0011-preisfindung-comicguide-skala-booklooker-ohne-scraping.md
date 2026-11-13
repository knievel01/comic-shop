# ADR-0011: Preisfindung: Comicguide-Skala, Booklooker-Marktpreis mit Beleg, kein Scraping

- **Status:** Akzeptiert
- **Datum:** 2026-10-27, konsolidiert 2026-11-13 (enthält frühere ADR-0017, ADR-0022, ADR-0028)

## Kontext
Der Inhaber nutzt Comicguide als Hauptquelle und schlägt ca. 50 % auf. Comicguide untersagt Data Mining
(§ 44b UrhG), eine Datenlizenz (Star Media) liegt nicht vor. Booklooker und ZVAB bieten keine Preis-API, ihre
`robots.txt` sperrt Programme. Ohne automatische Quelle bliebe pro Comic Handarbeit.

## Entscheidung
- **Skala:** Comicguide-Zustand 0–4 (ganze Stufen), Faktoren 1,5 / 1,0 / 0,4 / 0,2 / 0,1 zu Zustand 1.
  Preis = Basis Z1 × Zustandsfaktor × Aufschlag, gerundet auf ,50/,99, Mindestpreis. Alle Werte nur in
  `config/pricing.yaml`, nirgends hart codiert. Gespeichert werden Quelle, Basis, Faktor, Aufschlag, Endpreis, „überschrieben“.
- **Quelle (Standard `booklooker`):** Basis Z1 ist ein vergleichbares Booklooker-Angebot, mit **Pflicht-Beleg** (Link).
  Angebote sind Endkundenpreise, daher Aufschlag 1,0 für diese Quelle. Coverpreis × 2/3 (nur aktuelle Euro-Titel,
  nie DM) und Comicguide-Handwert bleiben wählbar. Wird eine Comicguide-Lizenz oder offizielle API verfügbar, wird
  dieses ADR angepasst.
- **Automatischer Vorschlag:** Die Anthropic-Websuche (auf `booklooker.de` und `zvab.com` beschränkt) liefert
  Fundstellen; der Dienst bildet den **Median** (mind. 2 Angebote) und nimmt das mittlere Angebot als Beleg. Claude
  rechnet nichts und schätzt nichts. Schlägt die Suche fehl, bleibt die Erkennung gültig. Die Fachkraft bestätigt
  oder überschreibt immer.
- **Kein Scraping:** Weder Comicguide noch Booklooker/ZVAB werden vom comic-helper oder n8n selbst abgerufen. Keine
  Comicguide-Texte oder -Bilder im Shop; Zustandstexte in eigenen Worten.
- Modell der Preissuche: Opus (`CLAUDE_MODEL`), siehe ADR-0010.

## Konsequenzen
- Preise beruhen auf Angeboten, nicht auf Verkaufspreisen; sie können über dem erzielbaren Preis liegen. Nachjustieren
  nach den ersten 100 Verkäufen über `pricing.yaml` und einen Shopify-Bestellexport (ADR-0025).
- Laufende KI-Kosten: etwa 0,29 $ je Comic mit Opus (Messung vom 04.11.2026, rund 580 $/Monat bei 2.000 Scans).
  Nach 4 Wochen Statistik prüfen; Sonnet (0,21 $, Ø 6 % Abweichung) ist die günstigere Alternative.
- Die Websuche muss in der Anthropic-Organisation aktiviert sein.

## Verworfene Alternativen
- Scraping oder eigener Abruf (rechtlich bzw. per `robots.txt` ausgeschlossen); eBay Browse API (eigenes Konto).
- Comicguide ohne Lizenz als Standard (Handarbeit je Exemplar); eigene Güteskala 1–5.
- Mittelwert statt Median (Fantasiepreise verzerren ihn); Sonnet/Haiku für die Suche (günstiger, ungenauer).

## Bezug
`config/pricing.yaml`, `comic_helper/pricing.py`, `marktpreis.py`, `docs/PREISFINDUNG.md`
