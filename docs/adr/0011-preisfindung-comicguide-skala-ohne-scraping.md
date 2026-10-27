# ADR-0011: Preisfindung nach Comicguide-Skala, zentral konfiguriert, kein Scraping

- **Status:** Akzeptiert
- **Datum:** 2026-10-27

## Kontext
Plan 6.3: Sepp nutzt Comicguide als Hauptquelle und schlägt ca. 50 % auf. Comicguide untersagt Data Mining
(§ 44b UrhG); Booklooker/ZVAB bieten keine passende Preis-API.

## Entscheidung
- Zustandsskala Comicguide 0–4 (nur ganze Stufen), Faktoren 1,5 / 1,0 / 0,4 / 0,2 / 0,1 zu Zustand 1.
- Preis = Basis Z1 × Zustandsfaktor × Aufschlag (1,5), gerundet auf ,50/,99, Mindestpreis.
- Basis Z1: Comicguide-Wert (von der Fachkraft eingetragen) oder bei aktuellen Euro-Titeln Coverpreis × 2/3.
  DM-Preise nie für die Coverpreis-Regel.
- Alle Werte nur in `config/pricing.yaml`, nirgends hart codiert.
- Kein Scraping von Comicguide; nur Direktlinks. Keine Comicguide-Texte/-Bilder im Shop, Zustandstexte in
  eigenen Worten.
- Gespeichert: Quelle, Basis, Faktor, Aufschlag, Endpreis, ggf. „überschrieben“.

## Konsequenzen
- Pro nicht lieferbarem Comic genau eine manuelle Preiseingabe, bis eine Datenlizenz von Star Media vorliegt.
- Nachjustieren nach den ersten 100 Verkäufen über `pricing.yaml`.

## Verworfene Alternativen
- Scraping (rechtlich ausgeschlossen); eigene Güteskala 1–5 (ersetzt durch Comicguide-Skala).

## Bezug
Plan 6.3; `config/pricing.yaml`, `comic_helper/pricing.py`, `docs/PREISFINDUNG.md`
