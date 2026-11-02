# ADR-0017: PoC: Booklooker-Angebotspreis als Standard-Preisquelle, mit Beleg

- **Status:** Akzeptiert (nur PoC, siehe `docs/POC.md`)
- **Datum:** 2026-11-02
- **Ergänzt:** ADR-0011 (für den PoC; ADR-0011 bleibt für den Zielbetrieb gültig)

## Kontext
Im PoC soll der Preis immer nach dem Booklooker-Angebot gebildet werden, und es soll nachvollziehbar
sein, woher der Preis kommt. ADR-0011 sieht Comicguide als Basis und Booklooker nur als Plausibilitäts-
prüfung vor. Booklooker bietet keine Preis-API, und die `robots.txt` von Booklooker sperrt nicht
freigegebene Programme vollständig (`User-agent: *` / `Disallow: /`). Ein automatischer Abruf aus dem
Workflow würde das umgehen und ist wie bei Comicguide ausgeschlossen.

## Entscheidung
- Neue Preisquelle `booklooker`. Sie ist im Review-Formular vorausgewählt (`standard_preisquelle`).
- Die Fachkraft öffnet den Booklooker-Direktlink (Titel + Untertitel), wählt ein vergleichbares Angebot
  (gleiche Ausgabe, Zustand 1) und trägt dessen Preis als Basis Z1 ein. Kein automatischer Abruf.
- Pflichtfeld **Beleg** bei Quelle `booklooker`: Link auf das gewählte Angebot (oder die Suche).
  Gespeichert im Sidecar und als S3-Metadatum `preis-beleg` (max. 300 Zeichen).
- Booklooker-Angebote sind bereits Endkundenpreise: Aufschlag für diese Quelle 1,0
  (`aufschlag_je_quelle` in `config/pricing.yaml`). Zustandsfaktor und Rundung gelten unverändert.
- Ein Coverpreis-Vorschlag wird weiter angezeigt, füllt das Feld aber nur noch, wenn die
  Standardquelle `coverpreis` ist.

## Konsequenzen
- Pro Exemplar eine manuelle Preiseingabe wie bisher, jetzt mit nachprüfbarem Beleg.
- Angebotspreise sind keine Verkaufspreise; sie können über dem tatsächlich erzielbaren Preis liegen.
- Für den Zielbetrieb `standard_preisquelle` auf `comicguide` zurücksetzen oder ein Folge-ADR schreiben.

## Verworfene Alternativen
- Automatischer Abruf der Booklooker-Suche – verstößt gegen deren `robots.txt`, keine API.
- eBay Browse API – eigenes Entwicklerkonto und neuer externer Dienst; für den PoC zurückgestellt.

## Bezug
`config/pricing.yaml`, `comic_helper/pricing.py`, `comic_helper/app.py`, `templates/review.html`,
`docs/PREISFINDUNG.md`, `docs/POC.md`.
