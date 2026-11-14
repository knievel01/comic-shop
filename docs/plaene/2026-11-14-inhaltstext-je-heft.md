# Plan: Inhaltstext je Heft, geschrieben in Workflow 01

Stand 14.11.2026. Zur Umsetzung in einer eigenen Sitzung in diesem Repo (`comic-shop`). Die Anzeige im Shop
(`comic-shop-headless`) ist Schritt 8 und wird dort umgesetzt.

> **Für die ausführende Sitzung:** `CLAUDE.md` und die ADRs 0005, 0010, 0011, 0012, 0027 vor dem Start lesen.
> Tests zuerst (rot, dann grün), ein Commit je Aufgabe, ADR-Änderungen im Commit der Umsetzung.

## Ziel

Jedes Comic-Produkt in Shopify bekommt einen kurzen, **eigenen** Inhaltstext (2 bis 4 Sätze, spoilerfrei). Er
entsteht beim Erfassen im Ablauf von Workflow 01, die Fachkraft prüft und ändert ihn im Review, und er geht
beim Anlegen des Produkts nach Shopify. Der Headless-Shop zeigt ihn unter „Worum geht’s?“ an.

## ⛔ Regel für jede Shopify-Änderung (Vorgabe von Roman)

Roman kennt sich mit Shopify nicht aus. Vor **jeder** Änderung am Produktiv-Shop (Einstellungen, Metafelder,
Produkte, Kanäle, Apps) gilt:
1. **Vorher in einfachem Deutsch erklären:** was genau sich ändert, wo im Shopify-Admin (Menüpfad), warum, was es
   bewirkt (Onlineshop, Checkout, die Kostüme im selben Shop „Mein Shop“, eBay), was es **nicht** berührt, wie man
   es rückgängig macht.
2. **Erst nach seinem ausdrücklichen OK** ändern, je Teilschritt einzeln.
3. **Danach berichten** und prüfen, dass eBay-Bestellungen (`sourceName: ebay`) normal eingehen (vorher und nachher).

Der eBay-Kanal (Marketplace Connect, `ebay-de`) darf nicht gestört werden. Die Sandbox darf gegen den
Shopify-Entwicklungsshop arbeiten (ADR-0027); der Produktiv-Shop nur nach Freigabe.

## Ausgangslage (geprüft)

- Workflow 01 (`workflows/comics-01-scan-ingest-und-erkennung.json`) ruft nur HTTP auf: `claim` → je Scan
  `POST /api/scans/{id}/recognize` → bei Fehler `…/fail`. Die Fachlogik liegt im comic-helper (ADR-0005).
- `recognize` (`app.py`) rendert das PDF, lässt Claude Cover und Rückseite lesen (`recognition.py`), holt den
  Preisvorschlag (`marktpreis.py`, darf scheitern, ohne die Erkennung zu blockieren) und setzt den Scan auf
  `offen`. Ergebnis im Sidecar `vorschlag` (S3, ADR-0004), Fortschritt als Tags (`STEPS`).
- Review (`/review/{id}`) bestätigt Titel, Zustand, Preis; `review_submit` schreibt `entscheidung`. Workflow 02
  ruft `to_shopify` → `Shopify.add_copy`: Produkt je Titel + Ausgabe + Verlag, weitere Exemplare werden Varianten.
- Beschreibung wird nur beim Anlegen gesetzt (`description_html`); Handtexte in Shopify bleiben erhalten.
- **Es gibt keinen Inhaltstext**, weder in Shopify noch im Sidecar noch im Prompt.
- ADR-0010 verlangt für die Erkennung „nichts raten, kein Wissen ergänzen“. Ein Inhaltstext braucht dagegen
  Wissen über das Heft. Das ist eine **Ausnahme**, die in ADR-0010 festgehalten werden muss (Aufgabe 1).
- ADR-0011: keine Texte von Comicguide übernehmen, kein Scraping. Gilt sinngemäß auch für Klappentexte.

## Entscheidungen

1. **Wo der Text entsteht:** im Schritt `inhalt` von `recognize`, nach der Preissuche, als Best-Effort (Fehler
   oder leerer Text blockieren die Erkennung nie, wie bei der Preissuche). So liegt der Entwurf schon vor, wenn
   der Scan im Review erscheint (keine Wettlaufsituation), und Workflow 01 behält seinen Aufbau. Zusätzlich ein
   eigener Endpunkt `POST /api/scans/{id}/inhalt` (idempotent, `?neu=1`) für „Inhalt neu schreiben“ im Review
   und für das Nachtragen. *Verworfen:* eigener n8n-Knoten nach `recognize` (Review könnte vor dem Text geöffnet
   und bestätigt werden; zweiter Fehlerpfad).
2. **Quellen, in dieser Reihenfolge:** (a) Text auf Cover oder Rückseite, **in eigenen Worten** zusammengefasst,
   nie abgeschrieben; (b) sicheres eigenes Wissen über genau diesen Band. Sonst leer. **Keine Websuche** und kein
   Abruf von Verlags- oder Katalogtexten (Urheberrecht, ADR-0011).
3. **Stil:** Deutsch, sachlich, Präsens, ohne direkte Anrede, 2 bis 4 Sätze, höchstens `inhalt.max_zeichen`;
   spoilerfrei; keine Wertung, keine Preis-, Zustands- oder Sammlerwert-Aussagen; keine Jahreszahlen, Autoren oder
   Figuren, die nicht belegt sind; kein HTML, keine Links.
4. **Ausgabe von Claude (strukturiert):** `text` (oder null), `quelle` (`rueckseite` | `wissen` | `keine`),
   `sicherheit` (0 bis 1). Der Dienst verwirft den Text, wenn `quelle = keine`, `sicherheit < inhalt.schwelle`,
   der Text zu lang ist oder Links/HTML enthält.
5. **Prüfpflicht:** Bei `quelle = wissen` muss die Fachkraft „Text geprüft“ ankreuzen, sonst lässt sich das
   Formular nicht bestätigen (wie der Pflicht-Beleg beim Preis). Leeren Text darf man immer bestätigen.
6. **Ein Text je Produkt:** Er gilt für alle Exemplare. In Shopify wird er nur gesetzt, wenn das Produkt noch
   keinen hat (Handtexte werden nie überschrieben).
7. **Ablage in Shopify:** Produkt-Metafeld `comic.inhalt` (Typ mehrzeiliger Text). Die Beschreibung bleibt unberührt
   (eBay liest Produktbeschreibungen; Generiertes und Handgeschriebenes bleiben getrennt). Das Metafeld braucht
   eine **Definition mit Storefront-Zugriff „lesen“**, sonst sieht der Headless-Shop es nicht (**Shopify-Änderung,
   Freigabe nötig**). *Rückfall, falls Roman die Definition nicht freigibt:* ein Absatz `<p><strong>Inhalt:</strong> …</p>`
   in der Beschreibung (Muster `LOT_MARKER`), den der Shop wie die Sammelposten-Notiz abtrennt.
8. **Modell:** eigene Variablen `INHALT_MODEL` (Start `claude-sonnet-5-5`) und `INHALT_EFFORT` (`low`), Rückfall
   `CLAUDE_MODEL`. Mit Rückseitenbild (kleine JPEG, `MODEL_MAX_EDGE`), ohne Preissuche. Kosten erwartet im
   niedrigen Cent-Bereich je Heft, in der Statistik als eigener Posten.
9. **Schalter:** `inhalt.aktiv` in `config/pricing.yaml`, zunächst `false`. Erst nach dem Probelauf (Aufgabe 6)
   und Romans Durchsicht der Texte auf `true`.

## Offen, vor dem Start mit Roman klären

- Ton des Textes (sachlich wie oben, oder lockerer im Stil von Comic-Sepp)?
- Metafeld `comic.inhalt` mit Storefront-Zugriff freigeben (Erklärung siehe Aufgabe 5) oder Rückfall Beschreibung?
- Die 8 bereits angelegten Hefte: von Hand im Shopify-Admin eintragen oder nachtragen lassen (Aufgabe 7)?

---

## Aufgabe 1: Konfiguration, ADRs, Grundgerüst

**Dateien:** `config/pricing.yaml`, `services/comic-helper/comic_helper/config.py`, `.env.example`,
`docs/adr/0010-…md`, `docs/adr/0012-…md`, `docs/adr/0011-…md`

**Schnittstellen (Produces):** `cfg["inhalt"]` = `{aktiv: bool, schwelle: float, max_zeichen: int, pruefpflicht: [str]}`;
`Settings.inhalt_model`, `Settings.inhalt_effort`.

- [ ] `config/pricing.yaml`: Block `inhalt:` mit `aktiv: false`, `schwelle: 0.8`, `max_zeichen: 600`,
  `pruefpflicht: [wissen]`. Kommentar: Schwelle und Länge sind Geschäftswerte und stehen nur hier.
- [ ] `Settings` um `inhalt_model` (`INHALT_MODEL`, Rückfall `anthropic_model`) und `inhalt_effort` (`INHALT_EFFORT`,
  Rückfall `anthropic_effort`) erweitern; beide in `.env.example` ohne Geheimnisse.
- [ ] ADR-0010 ergänzen: Inhaltstext als eigener Schritt mit eigenem Prompt, Quellen (Rückseite in eigenen Worten,
  sicheres Wissen), Ausnahme von „kein Wissen ergänzen“, Prüfpflicht bei Wissen, keine Websuche.
- [ ] ADR-0012 ergänzen: Metafeld `comic.inhalt` je Produkt, nur setzen wenn leer; Rückfall Beschreibungsabsatz.
- [ ] ADR-0011: ein Satz, dass Klappentexte und Verlagstexte nicht übernommen werden.
- [ ] `cd services/comic-helper && python -m pytest -q` bleibt grün. Commit „gemäß ADR-0010, ADR-0012“.

## Aufgabe 2: Inhaltstext erzeugen (`inhalt.py`)

**Dateien:** neu `services/comic-helper/comic_helper/inhalt.py`, neu `tests/test_inhalt.py`

**Schnittstellen (Produces):**
- `class InhaltErgebnis(BaseModel)`: `text: str | None`, `quelle: Literal["rueckseite","wissen","keine"]`, `sicherheit: float`.
- `def schreibe(client, proposal: dict, back_jpeg: bytes | None, model: str, effort: str, cfg: dict, usage_out: dict | None = None) -> dict | None`
  liefert `{"text", "quelle", "sicherheit"}` oder `None` (kein brauchbarer Text). Wirft nie; Fehler gehen als Log
  und `usage_out["fehler"]`.
- `def bereinigen(e: InhaltErgebnis, cfg: dict) -> dict | None`: reine Funktion für die Regeln aus Entscheidung 4.

- [ ] **Tests zuerst** (`test_inhalt.py`, ohne Netz, Claude-Client als Fake wie in `test_marktpreis_modell.py`):
  `test_bereinigen_verwirft_quelle_keine`, `…_unter_schwelle`, `…_zu_lang`, `…_html_und_links`,
  `…_trimmt_leerraum`; `test_prompt_enthaelt_regeln` (eigene Worte, spoilerfrei, nichts erfinden, Titel/Ausgabe/Verlag
  eingesetzt); `test_schreibe_gibt_bei_api_fehler_none_und_wirft_nicht`; `test_schreibe_ohne_rueckseite_nutzt_nur_wissen`.
- [ ] Prompt als Konstante in `inhalt.py` (Deutsch, Muster `marktpreis.PROMPT`/`recognition.SYSTEM_PROMPT`):
  Regeln aus Entscheidungen 2 und 3, ausdrücklich „Rückseitentext nie wörtlich übernehmen“ und „Im Zweifel leer lassen“.
- [ ] Aufruf wie in `recognition.recognize` (`client.beta.messages.parse`, `output_format=InhaltErgebnis`,
  Refusal-Fallback für `FALLBACK_MODELS`), Token-Verbrauch in `usage_out`.
- [ ] Tests grün, Commit.

## Aufgabe 3: In `recognize` einbauen, Review-Formular

**Dateien:** `app.py`, `templates/review.html`, `tests/test_flow.py`

**Schnittstellen:** Consumes `inhalt.schreibe`. Produces im Sidecar `vorschlag["inhalt"]` (`{text, quelle, sicherheit}`
oder `None`), `entscheidung["inhalt"]` (`{text, quelle, geprueft}`), Lauf-Eintrag `laeufe[].inhalt`
(`modell`, `input_tokens`, `output_tokens`, `sekunden`).

- [ ] **Tests zuerst** in `test_flow.py`: `test_recognize_schreibt_inhalt_in_den_vorschlag`;
  `test_recognize_bleibt_offen_wenn_inhalt_fehlschlaegt`; `test_recognize_ohne_schalter_ruft_inhalt_nicht_auf`;
  `test_review_speichert_inhalt_in_entscheidung`; `test_review_wissen_ohne_haken_wird_abgelehnt` (Fehlertext
  „Text geprüft bestätigen“); `test_review_leerer_inhalt_ist_erlaubt`.
- [ ] `STEPS` um `inhalt` (nach `preissuche`) erweitern, `_step(store, key, "inhalt")`, Tags wie bisher; Kachel in
  der Review-Liste zeigt den neuen Schritt (Textliste in `templates`/`static` prüfen).
- [ ] In `recognize` nach der Preissuche, nur bei `cfg["inhalt"]["aktiv"]`: Rückseitenbild (`model_images[1]`) und
  `proposal` an `inhalt.schreibe`; Ergebnis in `proposal["inhalt"]`, Lauf-Eintrag ergänzen.
- [ ] Neuer Endpunkt `POST /api/scans/{id}/inhalt` (`require_token`, `?neu=1`): lädt `bilder/<id>-2.jpg` aus S3,
  schreibt den Text neu in den Sidecar (nur Status `offen`/`fehler`), antwortet mit dem Text.
- [ ] `review.html`: Feld „Inhalt (für den Shop)“ als Textarea unter den Titelfeldern, vorbelegt mit
  `entscheidung.inhalt.text` oder `vorschlag.inhalt.text`; daneben Hinweis zur Quelle („aus dem Rückseitentext“ /
  „aus Modellwissen, bitte prüfen“); Checkbox „Text geprüft“ bei `quelle` in `pruefpflicht`; Knopf „Inhalt neu schreiben“.
  Zeichenzähler mit `max_zeichen`.
- [ ] `review_submit`: Feld `inhalt`, `inhalt_geprueft`; Regeln aus Entscheidung 5; Text auf `max_zeichen` und
  ohne HTML speichern (escapen).
- [ ] Tests grün, Commit „gemäß ADR-0010“.

## Aufgabe 4: Statistik und Doku des Ablaufs

**Dateien:** `statistik.py`, `tests/test_statistik.py`, `config/pricing.yaml` (Modellpreise vorhanden), `docs/ARCHITEKTUR.md`,
`docs/SCANNEN-UND-BESTAETIGEN.md`, `docs/PLAN.md`

- [ ] **Test zuerst:** `test_statistik_zaehlt_inhalt_als_eigenen_kostenposten`.
- [ ] `statistik.collect`: Teil `inhalt` neben `erkennung` und `preissuche` (Kosten aus `modellpreise_usd`).
- [ ] `docs/ARCHITEKTUR.md`: Schritt „Inhalt“ im Datenfluss und im Diagramm nach der Preissuche.
- [ ] `docs/SCANNEN-UND-BESTAETIGEN.md`: kurzer Abschnitt für die Fachkraft („Inhaltstext prüfen: Passt er zum
  Heft? Im Zweifel leer lassen“).
- [ ] `docs/PLAN.md`: Status-Zeile ergänzen. Tests grün, Commit.

## Aufgabe 5: Shopify: Metafeld schreiben und Definition (🔒 Freigabe)

**Dateien:** `shopify.py`, `tests/test_flow.py` (FakeShopifyAPI), `docs/SHOPIFY-EINRICHTUNG.md`

**Schnittstellen:** `Shopify.add_copy(..., inhalt: str | None = None)`; neue Abfragen `PRODUCT_BY_HANDLE` (um
`metafield(namespace: "comic", key: "inhalt") { value }` erweitert) und `METAFIELDS_SET`
(`metafieldsSet`, Typ `multi_line_text_field`). `to_shopify` reicht `entscheidung.inhalt.text` durch.

- [ ] **Tests zuerst** (FakeShopifyAPI): `test_neues_produkt_bekommt_inhalts_metafeld`;
  `test_weiteres_exemplar_ueberschreibt_vorhandenen_inhalt_nicht`; `test_vorhandenes_produkt_ohne_inhalt_bekommt_ihn`;
  `test_ohne_text_kein_metafieldsSet`; `test_inhalt_wird_nicht_in_die_beschreibung_geschrieben`.
- [ ] Umsetzen (idempotent, ein Fehler beim Metafeld darf das Anlegen der Variante nicht abbrechen, aber im Log
  und im Sidecar stehen).
- [ ] **Metafeld-Definition** (Namespace `comic`, Schlüssel `inhalt`, Besitzer Produkt, Typ mehrzeiliger Text,
  **Storefront-Zugriff: lesen**). Zuerst im Entwicklungsshop der Sandbox. **Im Produktiv-Shop nur nach Freigabe,**
  mit der Erklärung nach der Regel oben. Beispieltext für Roman: „Ich lege in Shopify ein zusätzliches Feld für
  Produkte an (Einstellungen → Benutzerdefinierte Daten → Produkte → Definition hinzufügen), Name ‚Inhalt‘. Es ist
  ein zusätzliches Textfeld am Produkt, es ändert keine Beschreibung, keine Preise, keinen Checkout und nichts am
  eBay-Kanal. Der ‚Storefront-Zugriff‘ erlaubt nur, dass unser eigener Shop das Feld lesen darf. Rückgängig:
  Definition wieder löschen, die Texte verschwinden dann vom Produkt.“ Ob die App-Berechtigungen reichen
  (`write_products`), vorher prüfen.
- [ ] `docs/SHOPIFY-EINRICHTUNG.md`: Schritte für Definition und Storefront-Zugriff. Tests grün, Commit „gemäß ADR-0012“.

## Aufgabe 6: Workflow 01, Sandbox, Probelauf, Freischaltung

**Dateien:** `workflows/comics-01-…json`, `docs/SANDBOX-MAC.md` (falls nötig)

- [ ] In der Sandbox (ADR-0027): `scripts/sandbox-orbstack.sh up`, `INHALT_*` und `inhalt.aktiv: true` nur dort.
- [ ] Workflow 01: Hinweis-Notiz „KI liest das Cover“ um „schreibt einen Kurztext zum Heft“ ergänzen; **Timeout
  des Knotens „KI liest das Cover“ prüfen** (zusätzlicher Claude-Aufruf), bei Bedarf erhöhen; Export mit
  `scripts/n8n-export.sh` (nie `--decrypted`), committen.
- [ ] Probelauf mit mindestens 10 Scans (deutsche Alben, Hefte, mindestens zwei wenig bekannte Titel und ein Heft
  ohne lesbaren Rückseitentext). Tabelle (Titel, Quelle, Sicherheit, Text) an Roman. Fehler (erfundene Handlung,
  falsche Figuren) führen zu strengerem Prompt oder höherer Schwelle, **nicht** zur Freischaltung.
- [ ] Erst nach Romans OK: `inhalt.aktiv: true` in `config/pricing.yaml`. Rollout nach ADR-0027: Merge nach
  `main`, dann `ssh -i ~/.ssh/id_ed25519_comics comicadmin@192.168.40.120 'sudo comics-update --tags apps'`.
  Die Metafeld-Definition im Produktiv-Shop vorher (Aufgabe 5, Freigabe).

## Aufgabe 7: Bestehende Hefte nachtragen (optional)

Die 8 angelegten Hefte haben noch keinen Text. Zwei Wege, Roman entscheidet:
- **Von Hand:** Im Shopify-Admin beim Produkt unter „Metafelder“ den Text eintragen (nach Aufgabe 5, kein Code).
- **Nachtragen per Dienst:** Endpunkt `POST /api/inhalt/nachtragen?limit=` und Review-Seite „Inhalte prüfen“:
  für jedes `aktiv/`-Exemplar, dessen Produkt noch kein Metafeld hat, ein Entwurf aus `bilder/<id>-2.jpg`, im Sidecar
  gespeichert (nicht in Shopify). Erst nach Prüfung und Bestätigung durch die Fachkraft wird das Metafeld gesetzt
  (🔒 Shopify-Schreibzugriff, vorher erklären). Tests analog Aufgabe 3 und 5.

## Aufgabe 8: Anzeige im Shop (Repo `comic-shop-headless`, eigene Sitzung)

**Schnittstelle:** Storefront-Feld `metafield(namespace: "comic", key: "inhalt") { value }` am Produkt.
- `src/lib/shopify.ts`: Feld in `PRODUCT_FIELDS`, `RawProduct.metafield`, `Comic.inhalt: string`.
- `src/pages/comic/[handle].astro`: Abschnitt „Worum geht’s?“ im Textblock, nur wenn `inhalt` gesetzt; Text als
  reiner Text mit Absätzen (nicht als HTML einsetzen). Beispieldaten in `fixtures.ts` mit und ohne Text.
- Prüfen mit Beispiel- und echten Daten, Desktop und 375 px, hell und dunkel. Ohne Definition oder Text bleibt die
  Seite unverändert (Metafeld `null`).

## Prüfen vor jedem Commit

```bash
cd services/comic-helper && python -m pytest -q
kubectl kustomize infra/k3s >/dev/null
bash -n os/build-iso.sh scripts/*.sh
```

## Risiken

- **Erfundene Inhalte** bei wenig bekannten Heften: Schwelle, Quellenangabe, Prüfpflicht, Schalter und Probelauf.
  Ein falscher Text im Shop ist schlimmer als keiner. Im Zweifel leer.
- **Urheberrecht:** Rückseitentexte nur in eigenen Worten und kurz; keine Verlags- oder Katalogtexte, keine Suche.
- **Kosten:** zusätzlicher Aufruf je Scan; in der Statistik sichtbar, Modell per `INHALT_MODEL` änderbar.
- **Mehrere Exemplare desselben Titels:** Text wird nur einmal je Produkt gesetzt; Wiederholungs-Entwürfe sind
  verschenkte Kosten. Optional später: vor dem Schreiben prüfen, ob das Produkt schon einen Text hat, und diesen
  vorbelegen statt neu zu erzeugen.
