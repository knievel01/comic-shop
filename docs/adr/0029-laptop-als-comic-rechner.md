# ADR-0029: Laptop als Comic-Rechner, WLAN nur als Fallback

- **Status:** Akzeptiert
- **Datum:** 2026-11-12

## Kontext
ADR-0001 und `hardware/README.md` gehen von einem Mini-PC aus. Der Go-Live (`docs/GO-LIVE.md`, E1) läuft auf einem
vorhandenen Laptop. Ein Laptop schläft bei geschlossenem Deckel, hat WLAN und meist kein „Power on after AC loss“.
Der Scanner ist noch nicht da, als Eingang dient eine Canon-Kamera per USB (ADR-0030).

## Entscheidung
- Neue Ansible-Rolle `laptop` (Schalter `comics_laptop`, Standard `true`): Deckel, Power-Taste und Leerlauf
  lösen kein Suspend aus, Sleep-Targets sind maskiert.
- Kabel-LAN bleibt der Standardweg (ADR-0002). WLAN ist Fallback: nur wenn `WIFI_SSID` und `WIFI_PASSWORD` in
  `/etc/comics/comics.env` stehen, schreibt die Rolle `/etc/netplan/60-comics-wifi.yaml` (Rechte 600) mit
  Route-Metrik 600, das Kabel hat Vorrang. Die ISO bleibt frei von Zugangsdaten (ADR-0003); der erste Lauf
  von ansible-pull braucht daher Kabel.
- `comics_scanner_enabled` ist standardmäßig `false`, bis ein SANE-Scanner angeschlossen ist.

## Konsequenzen
- Der Akku wirkt als einfache USV; Ladelimit (z. B. 80 %) im BIOS setzen, falls vorhanden.
- Ob das Laptop nach Stromausfall allein startet, ist modellabhängig und Teil der Abnahme (INSTALL.md).
- Die Kamera als Erfassung ist in ADR-0030 entschieden.

## Verworfene Alternativen
- WLAN-Zugang in der ISO – Geheimnis im öffentlichen Artefakt (ADR-0003).
- WLAN als Hauptverbindung – instabiler für Dauerbetrieb und Foto-Uploads.

## Bezug
ADR-0001, 0002, 0003, 0018; `os/ansible/roles/laptop`, `docs/GO-LIVE.md` E1
