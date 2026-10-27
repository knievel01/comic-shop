# comic-shop

Automatisierung für Sepps Comic-Shop: Ein A3-Scanner erzeugt pro Comic eine zweiseitige PDF,
n8n und der `comic-helper` erkennen Titel/Ausgabe/Verlag mit Claude, eine Fachkraft bestätigt
Zustand und Preis, das Exemplar landet als eigene Variante in Shopify. Verkäufe verschieben
den Scan in S3 nach `verkauft/`, jeden Morgen um 7 Uhr kommt eine Sammel-Mail.

| Dokument | Inhalt |
| --- | --- |
| [docs/PLAN.md](docs/PLAN.md) | Umsetzungsplan mit Status je Phase |
| [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md) | Komponenten, Datenfluss, Entscheidungen |
| [docs/INSTALL.md](docs/INSTALL.md) | Rechner von leerer SSD bis grünem `verify.sh` |
| [docs/BETRIEB.md](docs/BETRIEB.md) | Backup, Restore, Monitoring, Kosten |
| [docs/PREISFINDUNG.md](docs/PREISFINDUNG.md) | Zustandsskala, Preisformel, Quellen |
| [docs/SCANNEN-UND-BESTAETIGEN.md](docs/SCANNEN-UND-BESTAETIGEN.md) | Eine Seite für Sepp und die Schülerkräfte |

Konventionen für Claude Code: [CLAUDE.md](CLAUDE.md).
