# Preisfindung

Konfiguration: `config/pricing.yaml`. Code: `services/comic-helper/comic_helper/pricing.py`.

## Formel

```
Basis (Zustand 1) = Comicguide-Preis Z1
                    oder bei noch lieferbaren Titeln: Coverpreis × 0,6667
Preis             = Basis × Zustandsfaktor × Aufschlag (1,5)
                    gerundet auf den nächstgelegenen Preis mit ,50 oder ,99 (mindestens 2,00 €)
```

| Zustand | Bezeichnung | Faktor |
| --- | --- | --- |
| 0 | perfekt | 1,5 |
| 1 | sehr gut | 1,0 |
| 2 | gut | 0,4 |
| 3 | noch sammelwürdig | 0,2 |
| 4 | zum Wegwerfen zu schade | 0,1 |

Beispiel: Comicguide Z1 = 10,00 €, Zustand 2 → 10 × 0,4 × 1,5 = 6,00 € → **5,99 €**.

Nur ganze Stufen. Unvollständige Hefte („Zustand 5“) gehen nicht über den Shop.

**Sammelposten** (ADR-0012, mehrere gleiche Hefte mit Zustandsbereich): Der Faktor ist der Mittelwert der
Faktoren aller Zustände im Bereich (`sammelposten.preisregel`, alternativ `schlechtester` oder `bester`).
Beispiel: Z1 = 10,00 €, Zustand 1–3 → 10 × (1,0 + 0,4 + 0,2) / 3 × 1,5 = 8,00 € → **7,99 €** je Heft.

**KI-Zustandsempfehlung:** Claude schlägt anhand der Bilder eine Stufe 0–4 mit kurzer Begründung vor
(Skala aus `pricing.yaml`). Das Formular zeigt sie an und markiert die Stufe, wählt sie aber nicht vor:
den Zustand legt die Fachkraft am Exemplar fest. Gespeichert als S3-Metadatum `ki-zustand`, damit sich
die Trefferquote später auswerten lässt.

## Ablauf im Formular

> **Preisquelle (ADR-0011):** Vorausgewählt ist die Quelle `booklooker`. Die Fachkraft öffnet den
> Booklooker-Link, wählt ein vergleichbares Angebot (gleiche Ausgabe, Zustand 1) und trägt dessen
> Preis als Z1 ein, dazu als **Beleg** den Link auf das Angebot (Pflicht). Aufschlag für diese Quelle
> 1,0 (`aufschlag_je_quelle`), weil Angebote schon Endkundenpreise sind. Kein automatischer Abruf:
> Booklooker sperrt Programme per `robots.txt`. Mit einer Comicguide-Lizenz wird per Folge-ADR auf `comicguide` umgestellt.
>
> **Automatischer Vorschlag (ADR-0011):** Bei der Erkennung sucht die Anthropic-Websuche gebrauchte
> Angebote bei Booklooker und ZVAB (der Dienst ruft die Seiten nicht selbst ab). Der **Median** der
> gefundenen Preise (ohne Versand, mindestens 2 Angebote) füllt Preis, Beleg-Link und die Notiz vor.
> Die Notiz nennt Datum, alle Preise, Vorgehen und Links. Ändern geht jederzeit, der Knopf „Preis
> automatisch neu suchen“ wiederholt die Suche. Schalter und Grenzen: `marktpreis` in `pricing.yaml`.
>
> **Suchprompt (`marktpreis.py`):** Er ist so gebaut, dass auch kleinere Modelle brauchbar liefern. Gemessen
> an acht Comics mit je einem Lauf: Mediane von Sonnet 5.5 weichen im Schnitt etwa 7 %, die von Haiku
> 5.5 etwa 10 % von Opus 5.5 ab (vorher 26 % und 29 %), bei 6 bis 8 statt 2 bis 3 Angeboten. Kern:
> erst den Bandtitel überlegen (Händler führen Bände nach Titel, nicht nach Nummer), kurze Suchanfragen
> ohne Operatoren, Trefferlisten ganz lesen, Verlag und Einzelband als feste Kriterien, nicht nach
> Preis auswählen, keine Zwischenschritte in der Antwort. Die Antwort wird auch dann gelesen, wenn
> ein Modell Text oder Codeblöcke um das JSON legt. Vergleichen: `scripts/preissuche-vergleich.py`.

- **Noch lieferbar:** Claude liest Coverpreis, Währung und Jahr. Ist der Preis in Euro und das Heft
  höchstens 3 Jahre alt (`coverpreis.max_alter_jahre`), ist Z1 mit Coverpreis × 2/3 vorausgefüllt,
  Quelle `coverpreis`. Alte DM-Preise werden nie verwendet.
- **Immer:** Direktlinks zu Comicguide, ZVAB, Booklooker und GCD mit Titel und Untertitel,
  auch bei Coverpreis-Vorschlag zur Kontrolle.
- **Alle anderen:** Die Fachkraft trägt nur den Comicguide-Preis für Zustand 1 ein.
- **Kein Comicguide-Eintrag:** gedruckten Katalog prüfen, Quelle `katalog`.
- ZVAB und Booklooker dienen nur der Plausibilitätsprüfung (Angebots-, keine Verkaufspreise).
- Der Endpreis wird live angezeigt und kann überschrieben werden (wird als `preis-ueberschrieben=ja` gespeichert).

Gespeichert werden als S3-Metadaten: `preis-basis-z1`, `preis-quelle`, `preis-faktor`,
`preis-aufschlag`, `preis-final`, `preis-beleg` (Link, falls angegeben), dazu `zustand`.

## Nachjustieren

Nach den ersten 100 Verkäufen mit Sepp prüfen (Plan Phase 12). Daten:

Verkäufe stehen nur in Shopify (ADR-0025): Shopify-Admin → Bestellungen → Exportieren (CSV, Spalte
`Lineitem sku`). Die Preisdaten je Exemplar liegen in S3 und werden über die SKU zugeordnet:

```bash
# alle Exemplare in aktiv/ mit SKU und Preisdaten (tab-getrennt), per SKU mit dem Bestellexport verbinden
aws s3api list-objects-v2 --bucket "$S3_BUCKET" --prefix aktiv/ --query 'Contents[?ends_with(Key, `.pdf`)].Key' --output text \
 | tr '\t' '\n' | while read k; do
     aws s3api head-object --bucket "$S3_BUCKET" --key "$k" \
       --query 'Metadata.[sku,titel,ausgabe,zustand,"preis-quelle","preis-basis-z1","preis-final"]' --output text
   done
```

Werte in `config/pricing.yaml` ändern, committen, `sudo comics-update --tags apps`.
Die Tests in `tests/test_pricing.py` beschreiben das Beispiel oben und müssen dann angepasst werden.

## Quellen und Rechtliches

| Quelle | Automatisch? | Nutzung |
| --- | --- | --- |
| Comicguide (Star Media) | Nein. Data Mining laut Impressum untersagt (§ 44b UrhG) | Direktlink. **Datenlizenz bei info@comicguide.de anfragen.** Mit Lizenz entfällt die manuelle Z1-Eingabe |
| ZVAB / AbeBooks | Unklar | Direktlink. Bei AbeBooks nach Such-API fragen |
| Booklooker | API nur für Verkäufer | Direktlink. Optional später zweiter Verkaufskanal |
| Ximilar | API, aber Preise aus eBay/Mercari/Rakuten | nicht für Preise verwenden |

Keine Comicguide-Texte oder -Bilder im Shop. Die Zustandsbeschreibungen in `pricing.yaml` sind
eigene Formulierungen, die Bilder eigene Scans.

## Erkennung: Vergleichstest (Phase 6.1)

1. 50 repräsentative Comics scannen (deutsch/US, alt/neu, Hefte/Alben).
2. `testdaten/vergleich.csv` anlegen (Format im Kopf von `scripts/vergleichstest.py`), Ximilar-Spalte
   über die Ximilar-Demo ausfüllen.
3. `python3 scripts/vergleichstest.py testdaten/vergleich.csv --model claude-opus-5-5`
   Lohnt sich auch mit `--model claude-sonnet-5-5` und `--model claude-haiku-5-5` für den Kostenvergleich.
4. Entscheidung (nur Claude / Hybrid) und Modell in `docs/PLAN.md` festhalten, `CLAUDE_MODEL` setzen,
   ggf. `konfidenz_schwelle` anpassen, sodass „sicher“ eingestufte Treffer praktisch immer stimmen.

Grobe Kosten je Scan (2 Bilder ≈ 5.500 Input-, ≈ 700 Output-Tokens, Listenpreise Okt. 2026):
Opus 5.5 ≈ 3,6 US-Cent (≈ 72 $/Monat bei 2.000 Scans), Sonnet 5.5 ≈ 1,8 Cent (≈ 36 $), Haiku 5.5 ≈ 0,1 Cent (≈ 2 $).
Die tatsächlichen Werte gibt der Vergleichstest aus.
