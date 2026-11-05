# ADR-0026: Sammelposten: mehrere gleiche Hefte als eine Variante mit Zustandsbereich

- **Status:** Akzeptiert
- **Datum:** 2026-11-05
- **Ergänzt:** ADR-0012 (Variante je Exemplar), ADR-0013 (SKU), ADR-0011 (Preisformel), ADR-0018 (Foto-Upload)

## Kontext
Bisher wird jedes Heft einzeln gescannt und als eigene Variante mit Bestand 1 angelegt (ADR-0012).
Im Bestand liegen aber viele Hefte 20-, 30- oder 100-mal vor. Jedes davon zu scannen, zu prüfen und
einzeln einzustellen kostet viel Zeit. Die Kundschaft braucht bei solchen Heften kein Foto des
genauen Exemplars, wohl aber eine verlässliche Zusage zum Zustand.

## Entscheidung
- **Anzahl:** Beim Foto-Upload und im Review-Formular lässt sich eine Anzahl angeben (Standard 1,
  höchstens `sammelposten.max_anzahl`). Beim Upload steht sie bis zum Review als S3-Tag `anzahl` am Scan.
  Beim Scanner-Weg wird sie im Review eingetragen.
- **Sammelposten** heißt: Anzahl > 1. Fotografiert oder gescannt wird ein Beispielheft.
- **Zustand:** Bei einem Sammelposten sind mehrere Zustände wählbar. Gespeichert wird immer ein lückenloser
  Bereich: Wer 1 und 3 wählt, bekommt 1–3. Bei Anzahl 1 bleibt es bei genau einem Zustand.
- **Preis:** ein Preis je Heft. Faktor nach `sammelposten.preisregel` in `config/pricing.yaml` aus den
  Faktoren aller Zustände im Bereich, festgelegt auf `mittelwert`. Beispiel 1–3: (1,0 + 0,4 + 0,2) / 3 =
  0,5333. Der Endpreis bleibt überschreibbar.
- **Shopify:** Ein Sammelposten ist eine Variante im Produkt des Titels (wie bisher per Handle), mit
  Bestand = Anzahl. Optionswert „Zustand“: **„Sammelposten · Zustand 1–3“**, bei einem einzigen Zustand
  „Sammelposten · Zustand 2“. Die Option „Exemplar“ bekommt wie bisher den nächsten freien Buchstaben.
- **Text im Shop:** Die Produktbeschreibung bekommt beim ersten Sammelposten des Titels einmal den Absatz
  > **Sammelposten:** Von diesem Heft haben wir mehrere Exemplare. Bei der Variante „Sammelposten ·
  > Zustand 1–3“ erhalten Sie eines davon in Zustand 1 bis 3 (sehr gut bis noch sammelwürdig), nie
  > schlechter. Die Bilder dieser Variante zeigen ein Beispielexemplar; Ihr Heft kann davon leicht abweichen.

  Die übrige Beschreibung bleibt erhalten, auch Änderungen von Hand. Der Satz zu Einzelexemplaren lautet
  jetzt „Einzelne Exemplare haben wir selbst gescannt: Die Bilder zeigen genau das Heft, das Sie erhalten.“
- **SKU:** wie ADR-0013, mit dem Bereich statt einer Stufe: `asterix-12-z1-3-7f3a9c2b1234`.
  Die Kurz-ID ist die des Beispielscans.
- **S3:** Ein Sammelposten ist ein Scan und damit ein Objekt in `aktiv/`. Die Metadaten bekommen `anzahl`,
  `zustand` ist `2` oder `1-3`. Der Entscheidungsdatensatz im Sidecar enthält `zustaende` (Liste) und `anzahl`.

## Konsequenzen
- Viel weniger Arbeit bei Mehrfachbeständen: einmal scannen, einmal prüfen, einmal einstellen.
- Bild und Heft passen bei Sammelposten nicht mehr eins zu eins zusammen. Der Text im Shop sagt das deutlich.
- Der Mittelwert-Preis bedeutet: Ein Heft in Zustand 3 aus einem Posten 1–3 ist teurer, als es einzeln
  wäre, eines in Zustand 1 billiger. Wem das nicht passt, ändert `preisregel` (`schlechtester`, `bester`).
- Kommen später weitere Hefte desselben Titels dazu, entsteht ein neuer Sammelposten (neue Variante).
  Ein bestehender Bestand wird nicht automatisch erhöht, das geht in Shopify von Hand.
- Tagesmail und Statistik zählen weiterhin Scans, nicht Hefte.

## Verworfene Alternativen
- Jedes Heft einzeln scannen (bisher): zu viel Aufwand bei 20–100 gleichen Heften.
- Eine Variante je Zustand mit eigener Menge (z. B. 8 × Z1, 10 × Z2, 2 × Z3): genauer, verlangt aber,
  jedes Heft zu begutachten und zu zählen. Das spart kaum Zeit gegenüber dem Einzelscan.
- Preis nach dem schlechtesten Zustand: kundenfreundlich, aber nicht gewählt (Entscheidung vom 05.11.2026).

## Bezug
`config/pricing.yaml` (`sammelposten`), `comic_helper/pricing.py`, `comic_helper/shopify.py`,
`comic_helper/app.py`, `templates/review.html`, `templates/_hochladen_form.html`, `templates/liste.html`,
`docs/SCANNEN-UND-BESTAETIGEN.md`, `docs/PREISFINDUNG.md`.
