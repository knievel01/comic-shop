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
- Die Seite `/review/statistik` (Link in der Kopfzeile) liest alle Sidecars (eingang, aktiv, verkauft, papierkorb) und zeigt
  Kennzahlen, gesparte Zeit je Workflow, Läufe je n8n-Durchlauf und Kosten je Modell.
- Kosten werden **beim Anzeigen** aus Token und Preisliste berechnet (`statistik.modellpreise_usd` in
  `config/pricing.yaml`), nicht gespeichert; Preisänderungen gelten damit rückwirkend (ADR-0011: Werte nur dort).
- Gesparte Zeit = angenommene Handarbeit je Schritt (`statistik.handarbeit_minuten`) minus gemessene KI-Laufzeit
  minus Prüfzeit der Fachkraft (`pruefung_minuten`). Die Minutenwerte sind **Annahmen**, die Seite sagt das offen.
  Workflow 02 und 03 haben keine gemessene Laufzeit und zählen als 0. Gelöschte Comics verursachen Kosten, sparen nichts.

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
