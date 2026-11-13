# Shopify einrichten (Dev-Dashboard-App)

Grundlage: ADR-0012. Stand der Oberfläche: November 2026; Shopify baut sie öfter um, die Namen der
Menüpunkte können abweichen. Zugangsdaten gehören nie ins Repo und nie in den Chat.

## 1. App anlegen (einmalig, im Shopify-Admin und Dev Dashboard)

1. Im Shop-Admin anmelden. *Einstellungen → Apps → App-Entwicklung*. Alte benutzerdefinierte Apps lassen
   sich nicht mehr erstellen, der Knopf **„Apps im Dev Dashboard erstellen“** führt zu `dev.shopify.com`.
2. **App erstellen**: Name `comic-helper`. App-URL und „einbetten“ bleiben unverändert (der Dienst hat
   keine Oberfläche in Shopify).
3. Feld **Bereiche** (kommagetrennt):
   `write_products,write_inventory,read_orders,read_locations,read_publications`
4. **App erstellen**, im Dialog **Veröffentlichen** (erste Version, geht nicht in den App Store).
5. Auf der Übersichtsseite der App stehen **Client-ID** und **Client-Schlüssel** (Schlüssel verdeckt).

## 2. App im Shop installieren

Installationslink (Shop-Subdomain und Client-ID einsetzen):

```
https://admin.shopify.com/store/<shop>/oauth/install?client_id=<client-id>
```

Die Seite „App installieren“ listet die Zugriffe (Kund:innendaten, Mitarbeiter:innen, Produkte und
Bestellungen). Prüfen und **Installieren**. Danach erscheint die App unter *Apps*.

## 3. Zugangsdaten eintragen (auf dem Rechner, nicht im Repo)

In `~/.config/comics/comics.env` (Rechte 600), Werte selbst kopieren:

```
SHOPIFY_SHOP_DOMAIN=<shop>.myshopify.com
SHOPIFY_CLIENT_ID=<Client-ID aus der Übersicht>
SHOPIFY_CLIENT_SECRET=<Client-Schlüssel, Kopier-Knopf neben dem Feld>
```

`SHOPIFY_LOCATION_ID` und `SHOPIFY_PUBLICATION_IDS` folgen im nächsten Schritt. **`SHOPIFY_PUBLICATION_IDS`
im PoC leer lassen**, `config/pricing.yaml` steht auf `produkt_status: DRAFT`: Testcomics bleiben
Entwürfe und sind für Kundschaft nicht sichtbar.

Wer Benutzername und Passwort der Shopify-Anmeldung irgendwo abgelegt hat (z. B. in einer `.env`), löscht
sie: der Dienst braucht sie nicht, und sie gehören nicht auf die Platte.

## 4. Anmerkungen

- Ob die Verbindung steht, zeigt ein Aufruf mit dem Token, nicht die Installation allein.
- Weitere Bereiche später: neue Version im Dev Dashboard veröffentlichen, dann im Shop die neuen Zugriffe
  bestätigen.
- Keine Webhooks: Verkäufe werden nur in Shopify geführt (ADR-0025).
