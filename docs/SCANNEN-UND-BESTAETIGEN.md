# Scannen und Bestätigen – auf einer Seite

## Erfassen mit den Fußschaltern

1. **Schalter 1** treten: neues Heft (Ton). Das Heft aufs Pult legen.
2. **Schalter 2**: Cover fotografieren. Heft wenden, **Schalter 2**: Rückseite. Weitere Fotos sind möglich, das letzte
   gilt als Rückseite.
3. Nächstes Heft: wieder **Schalter 1**. Das letzte Heft des Tages schließt sich nach 5 Minuten Ruhe von selbst.
4. Auf der Seite „Hochladen“ steht, was als Nächstes kommt (nur am Scan-Rechner).

Ein Warnton heißt: Schalter 2 ohne Heft (erst Schalter 1), Kamera nicht erreichbar oder ein Heft mit nur einem Foto
(landet in `fehler/`). Nach der Erkennung heißt der Ordner wie das Heft (`/srv/scans/hochgeladen/<Heft>/`).

### Kamera einrichten (Canon EOS 450D, einmalig)

Die Kamera hängt per USB am Scan-Rechner, WLAN hat sie nicht. Ist sie an, nimmt Schalter 2 die Canon, sonst die Webcam.
Klappt die Canon nicht, gibt es einen Warnton, aber nie heimlich ein Webcam-Bild.

1. USB-Kabel (Mini-B auf USB-A) direkt an den Rechner, nicht über einen Hub.
2. Strom über einen Akku-Dummy mit Netzteil (Canon ACK-E5 oder Nachbau „LP-E5 Dummy“). Eine SD-Karte einlegen,
   die Fotos landen kurz darauf.
3. Menü: Abschaltautomatik **Aus**, Qualität **JPEG L** (kein RAW), Rückschau **Aus**, Autom. Drehen **Aus**.
   Steht sie auf RAW, sagt die Seite „Hochladen“ das.
4. Wählrad **Av**, Blende 8, ISO 200–400, Weißabgleich passend zum Licht.
5. Einmal scharf stellen, dann am Objektiv auf **MF** schalten. Die Höhe bleibt gleich, die Schärfe auch.
6. Kamera senkrecht von oben, darunter die dunkle, matte Unterlage. Das größte Heft füllt gut 80 % des Bildes.
   Zwei Lampen seitlich im 45°-Winkel, damit glänzende Cover nicht spiegeln.

Prüfen am Scan-Rechner: `gphoto2 --auto-detect` zeigt „Canon EOS 450D (PTP mode)“.

## Scannen (Scanner)

1. NAPS2 öffnen, Profil **„Comic A3, 2 Seiten“** wählen.
2. **Cover** auflegen → Scannen. **Rückseite** auflegen → Scannen.
3. **Speichern als PDF** in den Ordner `Scans/neu` (Name egal).
   Eine PDF = ein Comic = genau 2 Seiten (erst Cover, dann Rückseite).
4. Nächster Comic. Hochladen passiert automatisch innerhalb einer Minute.

Hat eine PDF nicht genau 2 Seiten, landet sie in `Scans/fehler`. Dann den Comic einfach neu scannen.

## Bestätigen

Im Browser **http://comics-01/review/** öffnen. Die Liste zeigt alle offenen Comics.
„Nachkontrolle“ heißt: Die KI ist sich nicht sicher, also genau hinschauen.

Pro Comic:

1. **Titel, Ausgabe, Verlag** mit dem Bild vergleichen und bei Bedarf korrigieren.
   Auf ein Bild klicken = groß anzeigen.
2. **Anzahl** prüfen. Bei mehreren gleichen Heften (Sammelposten) die Stückzahl eintragen,
   falls sie beim Hochladen noch nicht angegeben wurde.
   **Zustand** 0–4 wählen. Die Beschreibung steht unter jeder Stufe. Im Zweifel die schlechtere Stufe.
   Beim Sammelposten den besten und den schlechtesten Zustand im Stapel anklicken, z. B. 1 und 3:
   Im Shop steht dann „Sammelposten · Zustand 1–3“. Kein Heft darf schlechter sein als die schlechteste Stufe.
3. **Preis Zustand 1**:
   - Ist er schon ausgefüllt (Quelle „coverpreis“), nur prüfen.
   - Sonst auf **Comicguide** klicken, den Preis für **Zustand 1** ablesen und eintragen.
     ZVAB/Booklooker nur zum Vergleichen.
   - Nicht bei Comicguide? Im gedruckten Katalog nachsehen, Quelle **„katalog“** wählen.
4. Der Endpreis wird groß angezeigt. Nur überschreiben, wenn Sepp es so will.
5. **Inhaltstext prüfen** (Abschnitt „Inhalt“, nur wenn eingeschaltet): Passt der Text zum Heft? Er soll kurz sein und nichts
   verraten. Steht dort „aus Modellwissen, bitte prüfen“, muss **„Text geprüft“** angekreuzt werden, sonst lässt sich das
   Formular nicht bestätigen. Im Zweifel den Text löschen: leer ist erlaubt und besser als falsch. Mit **„Inhalt neu
   schreiben“** entsteht ein neuer Vorschlag (ersetzt den Text im Feld).
6. **Bestätigen und in den Shop.** Das nächste Exemplar öffnet sich automatisch.

Der Comic kommt danach von selbst in den Shop. Nichts weiter tun.

## Wenn etwas nicht stimmt

- Exemplar mit rotem **„Fehler“**: Steht dort „Seiten statt 2“, neu scannen.
  Sonst **„Erneut erkennen“** drücken und nach ein paar Minuten wieder schauen.
- Seite lädt nicht: Rechner an? Netzwerkkabel? Sonst Roman Bescheid geben.
- Falsch bestätigt: Roman Bescheid geben (Exemplar-Nummer steht unter den Bildern).
