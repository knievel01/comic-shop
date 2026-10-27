# comic-shop

Automatisierung für Sepps Comic-Shop: Ein A3-Scanner erzeugt pro Comic eine zweiseitige PDF,
n8n und der `comic-helper` erkennen Titel/Ausgabe/Verlag mit Claude, eine Fachkraft bestätigt
Zustand und Preis, das Exemplar landet als eigene Variante in Shopify. Verkäufe verschieben
den Scan in S3 nach `verkauft/`, jeden Morgen um 7 Uhr kommt eine Sammel-Mail.

| Dokument | Inhalt |
| --- | --- |
| [docs/PLAN.md](docs/PLAN.md) | Umsetzungsplan mit Status je Phase |
| [docs/adr/](docs/adr/README.md) | **Architekturentscheidungen (ADRs) – verbindliche Grundlage** |
| [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md) | Komponenten, Datenfluss, Zustände |
| [hardware/](hardware/README.md) | Hardware-Empfehlung, Scanner unter Linux |
| [future-improvements/](future-improvements/README.md) | Ausbaupläne, u. a. Skalierung auf 1 Mio. Comics |
| [docs/INSTALL.md](docs/INSTALL.md) | Rechner von leerer SSD bis grünem `verify.sh` |
| [docs/BETRIEB.md](docs/BETRIEB.md) | Backup, Restore, Monitoring, Kosten |
| [docs/PREISFINDUNG.md](docs/PREISFINDUNG.md) | Zustandsskala, Preisformel, Quellen |
| [docs/SCANNEN-UND-BESTAETIGEN.md](docs/SCANNEN-UND-BESTAETIGEN.md) | Eine Seite für Sepp und die Schülerkräfte |

Konventionen für Claude Code: [CLAUDE.md](CLAUDE.md).
