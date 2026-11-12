# ADR-0031: Installation per Netzwerkboot als Alternative zum USB-Stick

- **Status:** Akzeptiert
- **Datum:** 2026-11-12

## Kontext
ADR-0002 installiert über eine Autoinstall-ISO vom USB-Stick. Beim Go-Live auf dem Laptop stand kein
brauchbarer Stick bereit. Das Laptop hängt per Kabel im selben LAN wie der Rechner, der die ISO gebaut hat.

## Entscheidung
- `scripts/netboot.sh` bietet dieselbe ISO (inkl. nocloud-Seed) per UEFI-Netzboot an: dnsmasq als **proxyDHCP**
  und TFTP (signiertes Shim und GRUB), Kernel/initrd und ISO per HTTP von diesem Rechner.
  Der DHCP des Routers bleibt unverändert, Secure Boot kann an bleiben.
- Das Boot-Menü hat keinen Timeout: Die Installation löscht die ganze Platte des startenden Geräts und muss
  bestätigt werden. Firewall-Regeln (ufw) gelten nur für das lokale Netz und werden beim Beenden entfernt.
- Der USB-Stick bleibt der Standardweg (ADR-0002); Netzboot ist ein zusätzlicher, einmaliger Weg.

## Konsequenzen
- Der Client lädt die ISO (ca. 4 GB) in den RAM: mindestens 8 GB RAM, Kabel-LAN, UEFI mit Netzwerkboot.
  Über USB-LAN-Adapter nur, wenn das UEFI das unterstützt.
- Der Server muss während der Installation laufen. Danach `Ctrl+C`.
- Keine Geheimnisse im Netz: ISO enthält wie bisher nur den öffentlichen SSH-Schlüssel (ADR-0003).

## Verworfene Alternativen
- Router-DHCP ändern (Option 66/67) – Eingriff ins Heimnetz, nicht nötig.
- iPXE/Netboot-Tarball von Ubuntu – zusätzlicher Download ohne signierte Prüfsumme im Build.

## Bezug
ADR-0002, ADR-0003, ADR-0015; `scripts/netboot.sh`, `docs/INSTALL.md`
