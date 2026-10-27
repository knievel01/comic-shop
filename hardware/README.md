# Hardware

Hardware für den Betrieb nach den aktuell gültigen ADRs (ADR-0001: ein Rechner für Scan-Station und
Server, ADR-0007: Scan mit Scan-Software nach `/srv/scans/neu`). Ausbau für sehr große Bestände:
[`future-improvements/001-skalierung-1-million-comics.md`](../future-improvements/001-skalierung-1-million-comics.md).

Preise sind Rechercheergebnisse bzw. Schätzungen vom 27.10.2026 und vor dem Kauf zu prüfen.

| Dokument | Inhalt |
| --- | --- |
| [scanner-linux.md](scanner-linux.md) | Welche A3-Scanner unter Linux (SANE) tatsächlich laufen |

## Startausstattung (bis ca. 2.000 Scans/Monat, Plan-Mengenrahmen 20.000–40.000 Comics)

| Teil | Empfehlung | Mindestanforderung | ca. Preis |
| --- | --- | --- | --- |
| Rechner (Server + Scan-Station) | Business-Mini-PC, z. B. Lenovo ThinkCentre Tiny (M70q/M90q), ASUS NUC 15 Pro o. ä. | 64 Bit, 6–8 Kerne, **32 GB RAM**, 1 TB NVMe, Gigabit-LAN, USB 3 | 800–1.100 € (Schätzung) |
| Alternativ | vorhandener Office-PC | 4 Kerne, 8 GB RAM, SSD ≥ 120 GB (Plan 2.1) | 0 € |
| Scanner A3 | siehe [scanner-linux.md](scanner-linux.md): Epson Expression 12000XL (gebraucht) oder 13000XL Pro (neu) | SANE-Status „good“/„complete“ | gebraucht: offen · neu: ca. 4.300 € netto |
| USV | APC Back-UPS Pro / Eaton 5E, ca. 900 VA, mit USB | sauberes Herunterfahren bei Stromausfall | 150–250 € |
| Monitor, Tastatur, Maus | vorhanden / beliebig | Full HD | – |
| Netzwerk | Kabel, Gigabit-Switch | kein WLAN (wird nicht eingerichtet) | – |

### Begründungen

- **Kein RAID:** Alle Comic-Daten liegen in S3, Backups gehen nach S3, eine Neuinstallation dauert < 60 min
  (ADR-0002, ADR-0004). Eine einzelne gute NVMe reicht.
- **32 GB statt 64 GB RAM:** n8n, Postgres und comic-helper brauchen zusammen wenige GB. RAM war im Herbst 2026
  sehr teuer (64-GB-Kits 760–1.200 $). Bei Bedarf nachrüsten.
- **Business-Gerät statt Bastel-Mini-PC:** leise, Ersatzteile, Vor-Ort-Garantie, „Power on after AC loss“ im BIOS.
  Workstation-Mini-PCs wie Minisforum MS-A2 (16 Kerne, 10 GbE) sind für diese Last Overkill.
- **USV:** Der Stromausfall-Test (Plan 2.6) muss auch ohne USV bestehen; die USV verhindert aber, dass Postgres
  mitten im Schreiben abgewürgt wird. Anbindung per NUT ist noch nicht in Ansible (siehe future-improvements).

## Vor dem Kauf prüfen

1. Scanner-Modell in der SANE-Liste mit Status „good“ oder „complete“ (siehe [scanner-linux.md](scanner-linux.md)).
2. BIOS des Rechners: Boot von USB, „Power on after AC loss“.
3. Autoinstall-ISO auf dem echten Gerät testen (Plan, Offene Punkte 8).
