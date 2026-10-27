# ADR-0010: Erkennung mit Claude, Ximilar nur nach Vergleichstest

- **Status:** Vorgeschlagen
- **Datum:** 2026-10-27

## Kontext
Plan 6.1/6.2: Die Sammlung ist überwiegend deutsch (Ehapa, Carlsen, Bastei …), Ximilar deckt vor allem
US-Comics und Manga ab und liefert Preise nicht vom deutschen Markt.

## Entscheidung
- Claude mit Bildern von Cover und Rückseite, strukturierte Ausgabe, Sicherheit je Feld.
  Prompt-Regel: nichts raten, unlesbare Felder bleiben leer.
- Gesamtsicherheit = Minimum aus Titel, Ausgabe, Verlag; Schwelle `konfidenz_schwelle` (Start 0,80)
  → `sicher` / `nachkontrolle`.
- Modell und Effort per `CLAUDE_MODEL` / `CLAUDE_EFFORT` (Start `claude-opus-5-5`, `low`),
  serverseitiger Refusal-Fallback aktiv.
- Ximilar-Preise werden nie verwendet. Ximilar-Erkennung wird nur ergänzt, wenn der Vergleichstest
  (`scripts/vergleichstest.py`, 50 Comics) es empfiehlt.
- Kein automatischer Abgleich gegen Comic-Datenbanken ohne geprüfte, erlaubte Schnittstelle (ADR-0011).

## Konsequenzen
- Status wird `Akzeptiert`, sobald der Vergleichstest Modell, Schwelle und Hybrid-Frage geklärt hat;
  das Ergebnis kommt in dieses ADR oder ein Folge-ADR.
- Kosten je Scan hängen stark vom Modell ab (siehe `docs/PREISFINDUNG.md`).

## Verworfene Alternativen
- Nur Ximilar (deutsche Abdeckung ungewiss); Hybrid von Anfang an (ungeprüfter Mehraufwand).

## Bezug
Plan 6.1, 6.2; `comic_helper/recognition.py`
