# ADR-0028: PoC-Ergebnisse gelten im Zielbetrieb: Booklooker-Preis mit Beleg, Websuche-Vorschlag, Statistik, Fortschritt

- **Status:** Akzeptiert
- **Datum:** 2026-11-05
- **Ersetzt:** ADR-0017
- **Ergänzt:** ADR-0011 (Preisfindung), ADR-0022, ADR-0023, ADR-0024 (bisher nur PoC)

## Kontext
Mehrere Entscheidungen galten bisher nur für den PoC: Booklooker als vorausgewählte Preisquelle mit
Pflicht-Beleg (ADR-0017), der automatische Preisvorschlag per Anthropic-Websuche (ADR-0022), die
Statistik-Seite (ADR-0023) und der Live-Fortschritt von Workflow 01 (ADR-0024). Für den Zielbetrieb sah
ADR-0011 Comicguide als Basis vor. Die Datenlizenz von Comicguide (Star Media) liegt aber nicht vor, ohne
sie bliebe nur das Nachschlagen von Hand. Der PoC ist abgenommen (`docs/GO-LIVE.md`), die Entscheidungen
E2 bis E4 sind am 05.11.2026 gefallen.

## Entscheidung
- **Preisquelle:** Im Zielbetrieb ist `booklooker` vorausgewählt (`standard_preisquelle`), mit Pflicht-Beleg
  (Link) und Aufschlag 1,0 für diese Quelle, wie bisher in ADR-0017 beschrieben. Das gilt, bis eine
  Comicguide-Lizenz oder offizielle API vorliegt. Dann wird das per Folge-ADR umgestellt.
- **Preisvorschlag:** Der automatische Vorschlag aus ADR-0022 (Median gebrauchter Angebote bei Booklooker
  und ZVAB, gefunden per Anthropic-Websuche, kein eigener Abruf) gilt im Zielbetrieb.
- **Modell der Preissuche:** Opus wie im PoC (`marktpreis.modell` leer, also `CLAUDE_MODEL`). Erwartete
  Kosten laut Messung etwa 0,29 $ je Comic, rund 580 $ im Monat bei 2.000 Scans. Nach 4 Wochen mit der
  Statistik-Seite prüfen; Sonnet (0,21 $, Ø 6 % Abweichung) bleibt die günstigere Alternative.
- **Statistik-Seite (ADR-0023)** und **Live-Fortschritt (ADR-0024)** gelten im Zielbetrieb.
- **Shopify:** In der ersten Woche nach dem Go-Live werden Produkte als Entwurf angelegt
  (`shopify.produkt_status: DRAFT`) und von Hand freigeschaltet, danach `ACTIVE`.

## Konsequenzen
- Preise beruhen auf Angeboten, nicht auf Verkaufspreisen. Sie können über dem erzielbaren Preis liegen.
  Die Nachjustierung nach 100 Verkäufen (`docs/PREISFINDUNG.md`) bleibt wichtig.
- Laufende KI-Kosten für die Preissuche, sichtbar auf der Statistik-Seite.
- Comicguide bleibt Direktlink im Formular. ADR-0011 gilt weiter für Zustandsskala, Faktoren, Rundung und
  das Scraping-Verbot.
- Erinnerung: Nach der ersten Woche `produkt_status` auf `ACTIVE` setzen, erst in der Sandbox (ADR-0027).

## Verworfene Alternativen
- Comicguide nach ADR-0011: ohne Lizenz nur Handarbeit je Exemplar.
- Sonnet oder Haiku für die Preissuche: günstiger, aber ungenauer (Messung vom 04.11.2026); Opus gewählt.

## Bezug
`config/pricing.yaml` (`standard_preisquelle`, `aufschlag_je_quelle`, `marktpreis`, `shopify`),
`docs/PREISFINDUNG.md`, `docs/GO-LIVE.md`, ADR-0011, ADR-0017, ADR-0022 bis ADR-0024.
