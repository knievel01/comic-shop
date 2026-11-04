# ADR-0023: Statistik-Seite zeigt KI-Kosten, Laufzeiten und gesparte Handarbeit

- **Status:** Akzeptiert (PoC)
- **Datum:** 2026-11-04

## Kontext
Für die Vorführung und die Wirtschaftlichkeitsfrage sollen sichtbar sein: was ein Durchlauf kostet, wie lange er
dauert und wie viel Handarbeit die Workflows ersparen. Der Zustand liegt nur in S3 (ADR-0004), es gibt keine
Datenbank; die Modellwahl für die Preissuche hing an gemessenen Kosten (ADR-0022).

## Entscheidung
- Jede Erkennung und jede Preissuche hängt einen Eintrag an `laeufe` im Sidecar: Modell, Token, Websuchen, Sekunden,
  Zeitpunkt und – bei Aufruf aus Workflow 01 – die n8n-Ausführungsnummer (Header `X-N8N-Lauf`, gesetzt vom Knoten
  „Erkennen (Claude)“). Ältere Sidecars ohne `laeufe` werden aus `ki_info` gelesen (Token, keine Zeiten).
- Die Statistik (Link „Statistik“ in der Kopfzeile) hat zwei Seiten: `/review/statistik/kosten` (Kennzahlen, Kosten je
  n8n-Durchlauf, je Modell, Modellvergleich der Preissuche) und `/review/statistik/einsparung` (gesparte Zeit je Workflow
  und je n8n-Durchlauf). Sie lesen alle Sidecars (eingang, aktiv, verkauft, papierkorb).
- Kosten werden **beim Anzeigen** aus Token und Preisliste berechnet (`statistik.modellpreise_usd` in
  `config/pricing.yaml`), nicht gespeichert; Preisänderungen gelten damit rückwirkend (ADR-0011: Werte nur dort).
  Im Einsatz ist Opus; die gemessenen Kosten je Preissuche der anderen Modelle (`statistik.preissuche_vergleich`)
  stehen in Klammern daneben.
- Gesparte Zeit = Läufe × angenommene Minuten je Lauf (`statistik.gespart_minuten_je_lauf`, je Workflow 4 Min).
  Jeder Lauf spart diese Zeit, auch wenn er Token kostet; Kosten und Einsparung werden getrennt gezeigt und nicht
  verrechnet. Die Minutenwerte sind **Annahmen**. Gelöschte Comics verursachen Kosten, sparen nichts.

## Konsequenzen
- Kein neuer Dienst, keine neue Ablage; die Seite liest bei jedem Aufruf alle Sidecars (für PoC-Mengen ausreichend,
  bei tausenden Comics wäre ein Zwischenspeicher nötig).
- Workflow 01 wurde angepasst (Header am Erkennen-Knoten) und muss neu importiert und aktiviert werden.
- Läufe vor dieser Änderung haben keine Zeiten und keine n8n-Nummer.

## Verworfene Alternativen
- n8n-REST-API für Ausführungszeiten abfragen – braucht einen weiteren Zugang und Schlüssel, liefert keine Token/Kosten.
- Kosten im Sidecar speichern – würde bei Preisänderungen veralten.

## Bezug
ADR-0004, ADR-0011, ADR-0022; `services/comic-helper/comic_helper/statistik.py`, `templates/statistik.html`,
`scripts/n8n-workflows-generieren.py`.
