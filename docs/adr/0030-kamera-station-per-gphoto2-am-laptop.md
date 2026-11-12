# ADR-0030: Erfassung per Canon-Kamera am Laptop (gphoto2) statt Flachbett

- **Status:** Akzeptiert
- **Datum:** 2026-11-12

## Kontext
ADR-0007 setzt voraus, dass die Scan-Software PDFs mit genau 2 Seiten nach `/srv/scans/neu` legt. Der A3-Scanner
ist noch nicht da; stattdessen gibt es eine Canon-Kamera. Sie soll vom Laptop aus ferngesteuert werden, die Fotos
sollen direkt auf dem Laptop landen. `future-improvements/001` beschreibt die Kamera-Station bereits als Ausbau.

## Entscheidung
- Neue Ansible-Rolle `camera` (Schalter `comics_camera_enabled`, Standard `true`): gphoto2, udev-Regel für Canon
  (Gruppe `scanner`), gvfs-gphoto2-Monitor maskiert (der Desktop würde die Kamera sonst belegen).
- Skript `comics-capture`: Enter löst die Kamera per USB aus (`gphoto2 --capture-image-and-download`), erst Cover,
  dann Rückseite. Bilder werden nach EXIF gedreht, auf `comics_camera_max_edge` begrenzt und als **2-seitige PDF**
  (Seite 1 Cover, Seite 2 Rückseite) nach `/srv/scans/neu` geschrieben. `u` wiederholt das letzte Foto.
- Der bestehende Sync (`comics-scan-sync`, ADR-0007) bleibt unverändert und lädt die PDF hoch; die Rolle `sync`
  läuft, sobald Scanner oder Kamera aktiv sind.
- Der Foto-Upload über die Review-Oberfläche (ADR-0018) bleibt als zweiter Eingang bestehen, ist aber nicht
  der Standard.

## Konsequenzen
- Die Kamera muss von libgphoto2 mit Fernauslösung unterstützt werden (Modell vor dem Einsatz mit
  `comics-capture --probe` prüfen); sie muss im Modus M mit JPEG, festem Stativ und gleichmäßigem Licht stehen.
- Kein Zuschneiden, keine Live-Vorschau und kein Fußschalter in dieser Stufe (Fußschalter als USB-Tastatur
  wäre kompatibel, da Enter auslöst). Ausbau bleibt in `future-improvements/001`.
- Pro Comic sind zwei Auslösungen nötig; Zeit je Comic ist zu messen.

## Verworfene Alternativen
- Foto-Upload über das Handy als Standard – Nutzer will die Kamera am Laptop; mehr Handarbeit.
- Eigener Upload der JPEGs ohne PDF – würde ADR-0007 und Erkennung ändern, ohne Nutzen.
- Kamera per HDMI/Webcam-Modus – geringere Bildqualität, keine Einzelauslösung.

## Bezug
ADR-0007, ADR-0018, ADR-0029; `os/ansible/roles/camera`, `future-improvements/001-skalierung-1-million-comics.md`
