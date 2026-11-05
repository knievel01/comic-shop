# 001 – Skalierung auf 1 Million Comics

- **Stand:** Entwurf, 27.10.2026
- **Auslöser:** Gesamtbestand deutlich über dem Plan-Rahmen (20.000–40.000), Ziel bis zu 1.000.000 Comics,
  oder Scan-Durchsatz über ca. 2.000 Exemplare/Monat.
- **Betroffene ADRs:** 0001 (ein Rechner), 0007 (Scan-Upload), 0004 (S3-Zustand), 0010 (Erkennung),
  0011 (Preisfindung), 0012 (Shopify-Modell). Umsetzung erst nach neuen ADRs.

## Kernaussage

Der Server ist nicht der Engpass. Begrenzend sind **Erfassen** (Scannen) und **Bestätigen** (vor allem die
manuelle Comicguide-Preissuche). Skaliert wird über mehrere Scan-Stationen mit Kamera, eine Preisdaten-Lizenz
und einige Software-Anpassungen.

## Mengengerüst (Schätzungen)

| Größe | Wert |
| --- | --- |
| Zeit je Comic, A3-Flachbett (2 Seiten + Umlegen) | 45–60 s → ca. 60/h je Station |
| Zeit je Comic, Kamera-Station | 10–20 s → ca. 150–250/h je Station |
| 1 Mio. Comics, Flachbett | ca. 17.000 Stationsstunden (1 Station, Plan-Tempo: > 40 Jahre) |
| 1 Mio. Comics, Kamera | ca. 5.000 Stationsstunden; 3 Stationen × 6 h × 220 Tage ≈ 1,3–1,5 Jahre |
| Bestätigen bei manueller Preissuche (~45 s) | ca. 12.500 Arbeitsstunden |
| Tagesvolumen bei 3 Stationen | ca. 2.500–3.500 Scans, ca. 15–20 GB Upload/Tag (≈ 2 Mbit/s im Mittel) |
| S3-Speicher (PDF ~4 MB + 2 JPG ~1,5 MB) | ca. 5–6 TB → ca. 130 $/Monat Standard, mit Intelligent-Tiering deutlich weniger |
| Claude-Erkennung | Opus 5.5 ≈ 36.000 $, Sonnet 5.5 ≈ 18.000 $, Haiku 5.5 ≈ 1.000 $; Batch-API −50 % |

## Zielbild

```
                 ┌──────────────── zentraler Server (headless, K3s) ────────────────┐
 Station 1 ─┐    │  n8n, Postgres, comic-helper, Review-UI, Backup                    │
 Station 2 ─┼──> S3 eingang/  <─────────────────────────────────────────────────────┘
 Station n ─┘    (jede Station lädt selbst hoch, nur PutObject-Recht)
 Review-Arbeitsplätze: beliebige PCs/Tablets im LAN -> https://server/review/
```

## Maßnahmen

### A. Hardware

| Teil | Empfehlung | ca. Preis |
| --- | --- | --- |
| Zentraler Server | Business-Mini-PC, 6–8 Kerne, 32 GB RAM (später 64), 1 TB NVMe, headless | 800–1.100 € |
| USV | 900 VA mit USB, Abschaltung per NUT | 150–250 € |
| **Kamera-Station** (je Station) | | **1.300–1.800 €** |
| · Kamera | Canon EOS R50 + RF-S 18-45 (Fernauslösung per libgphoto2 verifiziert; Alternative Sony A6700) | 620–730 € |
| · Dauerstrom | Canon DR-E18 + Netzteil (statt Akku) | ca. 50–80 € |
| · Reprostativ | Säule mit Kamera-Arm (z. B. Kaiser RS 1/RS 2), Grundplatte mit Anschlagwinkel | ca. 200–400 € |
| · Licht | 2 LED-Flächenleuchten, CRI ≥ 95, mit Polfolie + Zirkular-Polfilter am Objektiv (Kreuzpolarisation gegen Glanz) | ca. 150–300 € |
| · Bedienung | USB-Fußschalter, Monitor | ca. 30 € + Monitor |
| · Stations-PC | kleiner Mini-PC, 16 GB RAM | ca. 250–400 € |
| Sonderfälle | ein A3-Flachbett (siehe `hardware/scanner-linux.md`) für Übergrößen/empfindliche Stücke | |
| Netzwerk | Gigabit-Switch, Kabel; Internet-Upload ≥ 20 Mbit/s | |

Ausbaustufen: Start = Server + USV + 1 Kamera-Station (ca. 2.300–3.200 €), danach je Station 1.300–1.800 €.

### B. Neue/geänderte Software

1. **Kamera-Aufnahme-Tool** (neue Ansible-Rolle `camera-station`): Fußschalter → `gphoto2 --capture-image-and-download`
   für Cover, Fußschalter → Rückseite, Live-Vorschau mit Schärfe-/Belichtungsprüfung, Zuschneiden auf den
   Anschlagwinkel, beide Bilder als 2-seitige PDF nach `/srv/scans/neu` (der bestehende Sync bleibt unverändert).
2. **Rollen trennen:** Inventar mit Gruppen `server` und `stations`; Stationen bekommen nur `base`, `desktop`,
   `camera-station`/`scanner`, `sync`. Eigene Hostnamen je Station, eigener Upload-Schlüssel je Station.
3. **S3-Zustand ohne Vollscans** (ADR-0004 anpassen): Status nicht nur als Tag, sondern im Schlüssel
   (`eingang/neu/`, `eingang/offen/`, …) oder ein Index-Objekt je Tag, damit Claim, Review-Liste und Tagesmail
   nicht für jedes Objekt `GetObjectTagging` aufrufen. Bei Zehntausenden offenen Fällen sonst zu langsam.
4. **Review-Liste paginieren**, Filter (Verlag, sicher/Nachkontrolle), Mehrbenutzer: Sperre „wird gerade bearbeitet“.
5. **Serien-Bestätigung:** gleiche Serie/gleicher Preis für viele Hefte in einem Schritt bestätigen.
6. **Erkennung günstiger:** Modell nach Vergleichstest; Batch-API für nicht eilige Scans; Prompt-Caching des
   System-Prompts.
7. **USV-Anbindung:** Rolle `ups` mit NUT, sauberes Herunterfahren von K3s.
8. **Speicherklassen:** Lifecycle alte `aktiv/` (auch Verkauftes, ADR-0025) nach Intelligent-Tiering bzw. Glacier Instant Retrieval.

### C. Organisatorisch / extern

1. **Comicguide-Datenlizenz (Star Media)** – bei 1 Mio. Comics Voraussetzung, nicht Option. Mit Lizenz wird der
   Z1-Preis automatisch vorgeschlagen und das Bestätigen dauert Sekunden statt Minuten.
2. **Shopify-Grenzen klären:** Nach meinem Kenntnisstand drosselt Shopify das Anlegen neuer Varianten ab
   50.000 Varianten im Shop auf 1.000 pro Tag (nicht verifiziert). Das würde den Durchsatz begrenzen →
   Shopify-Plan/Plus und Datenmodell (ADR-0012) vorher klären, ggf. nur verkaufsfähige Teilmenge listen.
3. **Lager-/Sortierlogik:** Lagerplatz als zusätzliches Metadatum (Kiste/Regal), sonst ist das verkaufte Heft
   bei 1 Mio. Exemplaren nicht auffindbar.
4. **Personal:** Erfassen und Bestätigen trennen (Schülerkräfte scannen, Fachkraft bestätigt in Serien).

## Vorgeschlagene ADRs (Entwürfe, noch nicht angelegt)

- *Zentraler Server und mehrere Scan-Stationen* – ersetzt ADR-0001.
- *Kamera-Station mit gphoto2 statt Flachbett als Standard-Erfassung* – ergänzt/ersetzt ADR-0007.
- *Status im Objektschlüssel statt nur als Tag* – ersetzt Teile von ADR-0004.
- *Automatischer Z1-Preis aus lizenzierten Comicguide-Daten* – ergänzt ADR-0011 (nach Lizenz).

## Offene Fragen

- Wie viele Comics sollen wirklich in den Shop, wie viele nur erfasst werden?
- Personal und Arbeitszeiten für Erfassung (bestimmt die Anzahl Stationen)?
- Shopify-Plan und Variantenlimits (siehe C.2)?
- Antwort von Star Media zur Datenlizenz?

## Quellen

- [libgphoto2, unterstützte Kameras](https://raw.githubusercontent.com/gphoto/libgphoto2/master/camlibs/ptp2/library.c)
  (Canon EOS R50, Sony A6700 mit Fernauslösung)
- [billiger.de: Canon EOS R50 + 18-45](https://www.billiger.de/products/4355441628-canon-eos-r50-schwarz-rf-s-18-45-mm),
  [PCGH: R50-Angebot](https://www.pcgameshardware.de/Amazon-Firma-17639/News/canon-eos-r50-systemkamera-mit-objektiv-deal-1494412/)
- [Bitdoze: Mini-PCs als Homeserver 2026](https://www.bitdoze.com/best-mini-pc-home-server/) (RAM-Preise Sept. 2026)
- [Notebookcheck: Minisforum MS-A2](https://www.notebookcheck.com/Minisforum-MS-A2-Kompakter-AMD-Mini-PC-mit-Workstation-Ambitionen-und-GPU-Upgrade-Option-im-Test.1057824.0.html)
- Scanner-Quellen: `hardware/scanner-linux.md`
