# ADR-0000: ADRs als verbindliche Entscheidungsgrundlage

- **Status:** Akzeptiert
- **Datum:** 2026-10-27, überarbeitet 2026-11-13

## Kontext
Entscheidungen zu Architektur, Datenhaltung, Sicherheit und Fachlogik waren über Plan, Code-Kommentare
und `docs/ARCHITEKTUR.md` verstreut. Für Claude Code und für Menschen muss eindeutig sein, was gilt
und warum. Nach 40 ADRs in zwei Wochen war das Gegenteil eingetreten: Feature-Details, Zwischenstände und
Ersetzungsketten (0009→0016→0025, 0033→0035, 0036→0037, 0038→0039) machten es schwer, den Ist-Stand zu finden.

## Entscheidung
- Ein ADR hält eine **tragende Entscheidung** fest: schwer rückgängig zu machen, nicht aus dem Code ablesbar,
  mit echten Alternativen. Format: `_vorlage.md`.
- Ein ADR beschreibt den **aktuellen Stand**. Ändert sich die Entscheidung, wird das ADR angepasst und der
  Verlauf steht in Git. Nur wenn eine Entscheidung ersatzlos wegfällt oder ein ganz anderes Thema ersetzt,
  entsteht ein neues ADR und das alte bekommt `Ersetzt durch ADR-NNNN`.
- Kein ADR für: einzelne Funktionen und Bildschirme der Review-Oberfläche, Konfigurationswerte
  (`config/pricing.yaml`), Zwischenlösungen ohne Bestand, Betriebsschritte (gehören nach `docs/`).
  Solche Dinge kommen als Absatz in das ADR des übergeordneten Themas oder in die Doku.
- Vor einem neuen ADR prüfen, ob ein bestehendes ergänzt werden kann.
- Code, Konfiguration und Doku müssen den akzeptierten ADRs entsprechen. Wer davon abweichen will,
  ändert zuerst das ADR.
- Übersicht und Zuordnung früherer Nummern: `docs/adr/README.md`.

## Konsequenzen
- Wenige, gepflegte ADRs statt eines Protokolls. Wer wissen will, wie es dazu kam, liest `git log -- docs/adr`.
- Die Nummern bleiben lückenhaft; Verweise in Commit-Messages auf entfernte Nummern löst die Tabelle im README auf.

## Verworfene Alternativen
- Alles als ADR festhalten, nie ändern (so entstanden die Ersetzungsketten).
- Entscheidungen nur in `docs/ARCHITEKTUR.md` sammeln (keine Begründung und Alternativen je Entscheidung).

## Bezug
`CLAUDE.md`, `docs/adr/README.md`
