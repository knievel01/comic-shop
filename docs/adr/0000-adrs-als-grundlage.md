# ADR-0000: ADRs als verbindliche Entscheidungsgrundlage

- **Status:** Akzeptiert
- **Datum:** 2026-10-27

## Kontext
Entscheidungen zu Architektur, Datenhaltung, Sicherheit und Fachlogik waren über Plan, Code-Kommentare
und `docs/ARCHITEKTUR.md` verstreut. Für Claude Code und für Menschen muss eindeutig sein, was gilt
und warum, damit spätere Änderungen nicht unbemerkt frühere Entscheidungen unterlaufen.

## Entscheidung
- Jede tragende Entscheidung steht als Architecture Decision Record (ADR) in `docs/adr/NNNN-titel.md`.
- Format: Status, Datum, Kontext, Entscheidung, Konsequenzen, verworfene Alternativen, Bezug.
- Status: `Vorgeschlagen` → `Akzeptiert` → ggf. `Ersetzt durch ADR-NNNN` oder `Verworfen`.
- ADRs werden **nicht umgeschrieben**, wenn sich die Entscheidung ändert: Es entsteht ein neues ADR,
  das alte bekommt den Status `Ersetzt durch ADR-NNNN`. Tippfehler und Präzisierungen sind erlaubt.
- Code, Konfiguration und Doku müssen den akzeptierten ADRs entsprechen. Wer davon abweichen will,
  schreibt zuerst ein ADR.
- Übersicht: `docs/adr/README.md`.

## Konsequenzen
- Änderungen dauern einen Schritt länger, sind dafür nachvollziehbar.
- `CLAUDE.md` verweist auf die ADRs als Grundlage für jede Arbeit im Repo.

## Verworfene Alternativen
- Entscheidungen nur in `docs/ARCHITEKTUR.md` sammeln (wird unübersichtlich, keine Historie je Entscheidung).

## Bezug
—
