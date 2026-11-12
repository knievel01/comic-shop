# ADR-0032: Cinnamon (Linux-Mint-Oberfläche) statt XFCE als Desktop

- **Status:** Akzeptiert
- **Datum:** 2026-11-12

## Kontext
ADR-0001 nennt einen minimalen XFCE-Desktop für die Scan-Station. Die Mitarbeitenden kennen Linux Mint
(Cinnamon). Der Comic-Rechner ist ein Laptop mit 8 GB RAM unter Ubuntu Server 24.04 (ADR-0029).

## Entscheidung
- Die Rolle `desktop` installiert `cinnamon-desktop-environment` (aus den Ubuntu-Paketquellen, kein Mint-Repository)
  mit LightDM statt `xfce4`. Auto-Login für den Scan-Benutzer startet die Sitzung `cinnamon`.
- Alles andere bleibt wie in ADR-0001: Auto-Login optional (`comics_scan_autologin`), `comics_desktop_enabled`.

## Konsequenzen
- Etwas mehr RAM im Leerlauf als XFCE. Bei 8 GB neben K3s, n8n und Postgres beobachten (Statistik, `free -h`).
- Ohne Mint-Repository kein Mint-Design (mint-themes u. ä.); das Aussehen ist Standard-Cinnamon.
- `docs/PLAN.md` und ADR-0001 sprechen weiter von XFCE; ADR-0001 wird nicht umgeschrieben (nur ergänzt).

## Verworfene Alternativen
- XFCE behalten – leichter, aber nicht gewünscht.
- Vollständiges Linux Mint als Basis – widerspricht ADR-0002 (Ubuntu-Autoinstall).
- GNOME (Ubuntu Desktop) – schwerer, bei 8 GB knapp.

## Bezug
ADR-0001, ADR-0029; `os/ansible/roles/desktop`
