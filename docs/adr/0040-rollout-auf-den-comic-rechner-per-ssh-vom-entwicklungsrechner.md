# ADR-0040: Rollout auf den Comic-Rechner per SSH vom Entwicklungsrechner

- **Status:** Akzeptiert
- **Datum:** 2026-11-13
- **Ergänzt:** ADR-0002, ADR-0027, ADR-0039

## Kontext
Der Comic-Rechner (Hostname `comic-server`, LAN-Adresse `192.168.40.120`) holt seinen Stand per `ansible-pull`
aus dem Repo (ADR-0002, `REPO_BRANCH=main`). Ausgelöst wird das mit `sudo comics-update` auf dem Rechner.
Bisher stand dafür nur der Weg „direkt am Rechner“ in der Doku. Der Entwicklungsrechner (MacBook, Sandbox nach
ADR-0039) löst den Namen `comics-01` nicht auf; die Anmeldung per Schlüssel ist aber eingerichtet
(`docs/INSTALL.md`, Benutzer `comicadmin`). `comicadmin` hat `sudo` für alle Befehle ohne Passwort.

## Entscheidung
- Der Rollout darf vom Entwicklungsrechner aus per SSH ausgelöst werden, auch durch Claude Code im Auftrag des Nutzers:
  ```bash
  ssh -i ~/.ssh/id_ed25519_comics comicadmin@192.168.40.120 'sudo comics-update --tags apps'
  ```
  Ohne `--tags apps` (z. B. für `os/`-Rollen) nur nach ausdrücklicher Freigabe.
- Reihenfolge bleibt wie in ADR-0027/0039: zuerst Sandbox prüfen, dann Änderung nach `main` mergen (der Rechner zieht
  nur `main`), dann `comics-update`. Vom Rechner wird nichts anderes ausgerollt als der Stand von `main`.
- Der private Schlüssel `~/.ssh/id_ed25519_comics` bleibt auf dem Entwicklungsrechner. Er steht nie im Repo, nie in
  Chats oder Tickets (ADR-0003). Im Repo steht nur der öffentliche Teil beim Bau der ISO (`SSH_KEYS_FILE`).
- Direkte Änderungen am Rechner (Dateien bearbeiten, Container von Hand starten) sind kein Weg: das Repo bleibt die
  Quelle (ADR-0002). Per SSH erlaubt sind außerdem lesende Prüfungen (Status, Logs, `scripts/verify.sh`).
- Die LAN-Adresse kann sich ändern (DHCP). Gilt sie nicht mehr, wird dieser ADR mit der neuen Adresse ergänzt, oder
  der Rechner bekommt eine feste Adresse bzw. einen auflösbaren Namen.

## Konsequenzen
- Rollout und Prüfung gehen vom Mac aus, ohne zum Rechner zu gehen.
- Wer den Schlüssel hat, hat wegen `sudo` ohne Passwort Root auf dem Comic-Rechner. Der Schlüssel gehört deshalb in den
  Schlüsselbund bzw. SSH-Agent und das Mac-Konto bleibt gesperrt (FileVault, Bildschirmsperre).
- SSH läuft nur im LAN (ADR-0008/0009: ufw nur für LAN-Netze, nichts aus dem Internet, ADR-0025).
- `docs/BETRIEB.md` und `docs/INSTALL.md` bleiben gültig; dieser ADR ergänzt nur den Weg vom Entwicklungsrechner.

## Verworfene Alternativen
- Nur direkt am Rechner ausrollen – jeder Rollout braucht dann einen Gang zum Rechner.
- Passwort-Anmeldung per SSH – widerspricht „nur per Schlüssel“ (`docs/INSTALL.md`).
- `sudo` auf `comics-update` beschränken – wäre sauberer, ist aber eine Änderung der Rolle `os/ansible`; bei Bedarf eigener ADR.

## Bezug
`docs/INSTALL.md` (Schritte 1–7, Konfiguration später ändern), `docs/BETRIEB.md`, `os/build-iso.sh`,
`os/autoinstall/user-data`, ADR-0002, ADR-0003, ADR-0008, ADR-0009, ADR-0025, ADR-0027, ADR-0039.
