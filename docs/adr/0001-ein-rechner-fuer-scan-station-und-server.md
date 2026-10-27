# ADR-0001: Ein Rechner für Scan-Station und Server

- **Status:** Akzeptiert (vorläufig)
- **Datum:** 2026-10-27

## Kontext
Plan 2.1, Entscheidung 1. Es gibt einen alten Office-Rechner. Scan-Station (Desktop für Schülerkräfte)
und K3s-Server könnten getrennt oder gemeinsam laufen.

## Entscheidung
Ein Rechner für alles: minimaler XFCE-Desktop mit Auto-Login für den Scan-Benutzer, K3s als
Systemdienst im Hintergrund. Alles als Ansible-Rollen modular, schaltbar über
`comics_desktop_enabled` / `comics_scanner_enabled`.

## Konsequenzen
- Einfachster Betrieb, eine Maschine zu pflegen.
- Später trennbar, ohne Umbau (Rollen abschalten).
- Ist der Scanner unter Linux nicht nutzbar (SANE), wird ein separater Scan-Rechner nötig, der nur nach
  S3 `eingang/` hochlädt (ADR-0007 bleibt gültig).

## Verworfene Alternativen
- Getrennte Rechner von Anfang an (mehr Hardware, mehr Pflege).

## Bezug
Plan 2.1; `os/ansible/site.yml`, `group_vars/all.yml`
