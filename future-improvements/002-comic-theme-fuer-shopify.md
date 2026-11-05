# 002 – Webshop im Comic-Design als Shopify-Theme

- **Stand:** Entwurf, 05.11.2026
- **Auslöser:** Nach dem Go-Live (`docs/GO-LIVE.md`), wenn der Shop mit dem Standard-Theme läuft und die ersten
  Produkte freigeschaltet sind.
- **Betroffene ADRs:** 0012 (Variante je Exemplar), 0026 (Sammelposten), 0025 (kein Zugang aus dem Internet),
  0011 (Comicguide-Texte nicht übernehmen). Umsetzung erst nach einem eigenen ADR.

## Kernaussage

Der Webshop bekommt die Comic-Optik der Review-Oberfläche (Bangers, Zackenstern, Panels, Papierhintergrund).
Umgesetzt wird das als **eigenes Shopify-Theme**, nicht als eigene Website: gleiche Optik für etwa ein Fünftel
des Aufwands. Hosting, Warenkorb, Checkout, Suche, Rechtstexte und SEO bleiben bei Shopify. Am Comic-Rechner und
an der Architektur ändert sich nichts.

Geschätzter Aufwand: **4–7 Arbeitstage**.

## Ziel

- Ein Shop, der wie die Review-Oberfläche aussieht und auf dem Handy gut funktioniert.
- Produktseiten, die Einzelexemplare mit ihren eigenen Scans zeigen und Sammelposten klar erklären.
- Filter nach Verlag, Sprache, Format und Zustand.
- Kein neuer Dienst, kein eigenes Hosting, keine Änderung an comic-helper oder Workflows.

## Vergleich der Wege

| | Shopify-Theme (empfohlen) | Eigene Website (headless, Storefront API) |
| --- | --- | --- |
| Aufwand | 4–7 Tage | 3–5 Wochen, danach laufende Pflege |
| Hosting | Shopify | extern (z. B. Shopify Oxygen, Cloudflare Pages); nicht auf dem Comic-Rechner (ADR-0025) |
| Warenkorb, Checkout, Kundenkonto | Shopify | Shopify-Checkout über die Cart API, Rest selbst |
| Suche, Filter, SEO, Rechtstexte, Cookie-Hinweis | von Shopify bzw. App | selbst |
| Neue Zugangsdaten | keine | Storefront-Access-Token |
| Wiederverwendung aus der Review-Oberfläche | Design-Tokens, Schriften, Formen | nur das Aussehen (ca. 10–20 %) |

Headless lohnt sich erst bei Funktionen, die ein Theme nicht kann (z. B. eigene Seriensuche mit eigener Datenbasis).

## Maßnahmen

### 1. Grundlage (0,5 Tage)
- Theme **Dawn** (Online Store 2.0, kostenlos) duplizieren, lokal mit der Shopify CLI (`shopify theme dev`)
  gegen den Entwicklungsshop der Sandbox entwickeln (ADR-0027).
- Theme-Quelltext im Repo unter `shop-theme/`, Veröffentlichung per `shopify theme push`. Keine Zugangsdaten im Repo
  (ADR-0003); die CLI meldet sich interaktiv an.

### 2. Design übernehmen (1–1,5 Tage)
- Design-Tokens aus `services/comic-helper/comic_helper/templates/base.html` in die Theme-CSS übertragen:
  Farben (`--ink`, `--red`, `--yellow`, `--paper`, `--seite`), Strich und Druckschatten, Punktraster, Papierfaser.
- Schriften Bangers und Barlow Condensed (OFL, liegen unter `static/fonts/`) als Theme-Assets einbinden.
- Zackenstern (`--burst`) für Preise und Hinweise wie „Sammelposten“, Panels für Produktkarten,
  Comic-Überschriften für Kategorien.
- Lesbarkeit prüfen: Kontrast der Fließtexte, Größen auf dem Handy, Fokus-Rahmen für Tastatur.

### 3. Produktseite (2–3 Tage, Hauptaufwand)
- **Variantenauswahl:** Optionen „Zustand“ und „Exemplar“ verständlich darstellen. Ausverkaufte Varianten
  ausblenden (Bestand 0, ADR-0012).
- **Bilder je Variante:** Beim Wechsel des Exemplars die zugehörigen Scans (Cover und Rückseite) zeigen. Jede
  Variante hat ihr eigenes Bild (`mediaSrc` beim Anlegen); die Galerie muss nach der gewählten Variante filtern.
- **Sammelposten (ADR-0026):** Varianten „Sammelposten · Zustand 1–3“ deutlich kennzeichnen (Stern
  „Sammelposten“), den Erklärtext aus der Beschreibung direkt an der Auswahl zeigen, Bilder als
  „Beispielexemplar“ beschriften, Stückzahl „noch x Stück“ anzeigen.
- **Zustandsskala:** Die Beschreibungen der Stufen 0–4 stehen schon in der Produktbeschreibung
  (`shopify.description_html`); als aufklappbaren Block gestalten.
- Viele Varianten je Titel (bis 2.048): Auswahl als Liste mit Vorschaubild statt Dropdown.

### 4. Katalog, Filter, Suche (1 Tag)
- App **Search & Discovery** (kostenlos) für Filter: Verlag (Hersteller), Sprache und Format (Tags), Zustand
  (Option), Preis, Verfügbarkeit.
- Kategorieseiten (z. B. nach Verlag oder Serie) als Collections mit automatischen Regeln über Tags.
- Produktkarten im Panel-Stil mit Preis im Stern, „ab“-Preis bei mehreren Varianten.

### 5. Rest und Abnahme (0,5–1 Tag)
- Startseite, Kopf und Fuß, Warenkorb im Comic-Stil; Checkout bleibt Shopify-Standard (dort nur Logo und Farben).
- Rechtstexte (Impressum, AGB, Widerruf, Datenschutz) über die Shopify-Richtlinienseiten.
- Test auf Handy und Desktop, mit echten Daten aus der Sandbox: Einzelexemplar, Sammelposten, Titel mit vielen
  Varianten, ausverkaufte Varianten.
- Veröffentlichung: Theme im echten Shop hochladen, Vorschau prüfen, dann aktivieren. Das bisherige Theme bleibt
  als Rückfall erhalten.

## Betroffene ADRs

- Neues ADR „Webshop als eigenes Shopify-Theme im Repo“ (Theme-Quelltext unter `shop-theme/`, Shopify CLI,
  erst Entwicklungsshop, dann echter Shop).
- 0012/0026: keine Änderung am Datenmodell; das Theme stellt es nur dar.
- 0025: unberührt, der Comic-Rechner bleibt ohne Zugang aus dem Internet.
- 0011: keine Comicguide-Texte oder -Bilder im Shop (Zustandstexte sind eigene Worte).

## Offene Fragen

1. Soll der Checkout zusätzlich angepasst werden (nur mit Shopify Plus über Logo und Farben hinaus möglich)?
2. Kategorien: nach Verlag, nach Serie oder beides? Serie ist bisher kein eigenes Feld (nur Titel); ggf. ein
   Tag `serie:<name>` beim Anlegen ergänzen (Änderung in `shopify.py`, eigenes ADR).
3. Ein Hinweis „Sammelposten“ in der Produktkarte braucht die Information auf Produktebene; reicht ein Tag
   `sammelposten`, den `shopify.py` beim ersten Sammelposten setzt?
4. Startseite: redaktionelle Inhalte (Neuzugänge, Empfehlungen) gewünscht, und wer pflegt sie?
