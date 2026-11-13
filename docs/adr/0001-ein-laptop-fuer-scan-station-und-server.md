# ADR-0001: Ein Laptop für Scan-Station und Server

- **Status:** Akzeptiert (vorläufig)
- **Datum:** 2026-10-27, konsolidiert 2026-11-13 (enthält frühere ADR-0029, ADR-0032)

## Kontext
Scan-Station (Desktop für Schülerkräfte) und K3s-Server könnten getrennt oder gemeinsam laufen. Der Go-Live
läuft auf einem vorhandenen Laptop mit 8 GB RAM statt auf einem Mini-PC. Ein Laptop schläft bei geschlossenem
Deckel, hat WLAN und meist kein „Power on after AC loss“. Die Mitarbeitenden kennen Linux Mint.

## Entscheidung
- Ein Rechner für alles: Desktop mit Auto-Login für den Scan-Benutzer, K3s als Systemdienst im Hintergrund.
  Alles als Ansible-Rollen, schaltbar über `comics_desktop_enabled`, `comics_scanner_enabled`,
  `comics_camera_enabled`, `comics_laptop`.
- **Laptop-Betrieb:** Deckel, Power-Taste und Leerlauf lösen kein Suspend aus (Rolle `laptop`). Kabel-LAN ist der
  Standardweg; WLAN nur als Fallback mit niedrigerer Priorität, Zugangsdaten nur aus `/etc/comics/comics.env`
  (nie in der ISO, ADR-0003). Der erste `ansible-pull`-Lauf braucht daher Kabel.
- **Desktop:** Cinnamon (`cinnamon-desktop-environment` aus den Ubuntu-Quellen, kein Mint-Repository) mit LightDM
  statt XFCE.
- `comics_scanner_enabled` ist aus, bis ein SANE-Scanner da ist; bis dahin dient die Kamera (ADR-0007).

## Konsequenzen
- Einfachster Betrieb, eine Maschine zu pflegen; der Akku wirkt als einfache USV.
- Später trennbar, ohne Umbau (Rollen abschalten). Ist ein Scanner unter Linux nicht nutzbar, wird ein
  separater Erfassungsrechner nötig, der nur nach S3 `eingang/` hochlädt (ADR-0007 bleibt gültig).
- Cinnamon braucht etwas mehr RAM als XFCE; bei 8 GB neben K3s, n8n und Postgres beobachten.
- Ob das Laptop nach Stromausfall allein startet, ist modellabhängig und Teil der Abnahme.

## Verworfene Alternativen
- Getrennte Rechner von Anfang an (mehr Hardware, mehr Pflege).
- WLAN als Hauptverbindung (instabiler für Dauerbetrieb und Uploads).
- XFCE behalten, Linux Mint als Basis (widerspricht ADR-0002), GNOME (bei 8 GB zu schwer).

## Bezug
`os/ansible/site.yml`, `group_vars/all.yml`, Rollen `desktop`, `laptop`; `hardware/README.md`, `docs/INSTALL.md`
