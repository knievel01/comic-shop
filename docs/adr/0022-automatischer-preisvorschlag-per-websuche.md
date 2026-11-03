# ADR-0022: Automatischer Preisvorschlag aus Booklooker/ZVAB per Anthropic-Websuche

- **Status:** Akzeptiert (PoC)
- **Datum:** 2026-11-03
- **Ergänzt:** ADR-0017 (Booklooker als PoC-Preisquelle), ADR-0011 (Preisfindung)

## Kontext
Im PoC musste der Preis je Exemplar von Hand bei Booklooker gesucht werden (ADR-0017). Gewünscht ist ein
automatischer Vorschlag: Mittelpreis aus Angeboten bei Booklooker oder ZVAB, mit Notiz zur Herleitung.
Die `robots.txt` beider Portale sperrt Programme (`User-agent: *`; Booklooker `Disallow: /`, ZVAB
`/servlet/`, `/search/`). Ein eigener Abruf durch den comic-helper oder n8n bleibt deshalb ausgeschlossen
(ADR-0017, bestätigt).

## Entscheidung
- Die Suche übernimmt das Websuch-Werkzeug der Claude-API (`web_search_20250305`, auf `booklooker.de`
  und `zvab.com` beschränkt). Der comic-helper ruft diese Seiten nie selbst auf.
- Claude liefert nur Fundstellen (Preis, Link, Kurzbeschreibung), nichts Berechnetes und keine geschätzten
  Preise. Der Dienst filtert auf die beiden Portale, entfernt Doppelte und Ungültiges.
- **Median** der Angebotspreise (ohne Versand) = Basis Z1, Quelle `booklooker`, Aufschlag 1,0 wie bisher
  (ADR-0017). Mindestens 2 Angebote, sonst kein Vorschlag (dann bleibt es beim Coverpreis-Vorschlag
  oder der Handeingabe).
- Beleg-Link = Angebot, das dem Median am nächsten liegt. Die **Notiz** im Review-Formular (vorbelegt,
  änderbar, im Sidecar gespeichert) nennt Datum, Anzahl, alle Preise, Vorgehen und Links.
- Läuft bei der Erkennung mit, schlägt die Suche fehl, bleibt die Erkennung gültig. Im Review gibt es
  „Preis automatisch neu suchen“ (`POST /review/{id}/preis-suchen`) für bereits erkannte Exemplare.
- Schalter und Grenzen in `config/pricing.yaml` unter `marktpreis` (`aktiv`, `min_angebote`, `max_suchen`).

## Konsequenzen
- Vorschläge sind Näherungen aus Suchtreffern: Angebots- statt Verkaufspreise, Ausgabe und Zustand der
  Fundstelle können abweichen. Die Fachkraft prüft am Beleg und bestätigt oder überschreibt (Pflichtschritt
  bleibt, nichts geht ohne Bestätigung in den Shop).
- Zusatzkosten je Comic: Websuchen (bis zu `max_suchen`) plus Tokens. Die Websuche muss in der
  Anthropic-Organisation aktiviert sein.
- Für den Zielbetrieb weiter Comicguide (ADR-0011); eine Lizenz oder offizielle API ersetzt dieses ADR.

## Verworfene Alternativen
- Eigener Abruf von Booklooker/ZVAB – verstößt gegen robots.txt.
- eBay Browse API – eigenes Entwicklerkonto, andere Preisquelle.
- Mittelwert statt Median – einzelne Fantasiepreise (z. B. 49,79 € neben 3–10 €) verzerren ihn.

## Bezug
`comic_helper/marktpreis.py`, `comic_helper/app.py`, `templates/review.html`, `config/pricing.yaml`,
`docs/PREISFINDUNG.md`, ADR-0011, ADR-0017.
