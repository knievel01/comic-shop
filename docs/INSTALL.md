# Installation des Comic-Rechners

Ziel: von leerer SSD bis grünem `verify.sh` in unter 60 Minuten. Manuelle Eingriffe sind nur beim
BIOS (Schritt 3) und bei den Geheimnissen (Schritt 6) nötig.

## Voraussetzungen

- Rechner: 64-Bit, 4 Kerne, 8 GB RAM, SSD ≥ 120 GB, Gigabit-LAN per Kabel (WLAN wird nicht eingerichtet).
  Empfehlung und Einkaufsliste: `hardware/README.md`.
- USB-Stick ≥ 8 GB.
- Zugriff auf den Passwort-Manager (Eintrag „Comic-Rechner comics.env“).
- Der Scanner steht auf der SANE-Liste (https://sane-project.org → „Supported Devices“).
  **Vor dem Kauf prüfen**, Ergebnis der Recherche in `hardware/scanner-linux.md`
  (Plustek OpticSlim 1180 läuft laut Recherche nicht unter Linux). Ist der Status nicht
  „good“/„complete“, einen separaten Scan-Rechner einplanen (siehe ADR-0001).

## 0. Einmalig: ISO-Release vorbereiten (nur wer das Repo pflegt)

1. Im GitHub-Repo unter *Settings → Secrets and variables → Actions → Variables*:
   - `ADMIN_SSH_KEYS`: öffentliche SSH-Schlüssel der Admins (eine Zeile pro Schlüssel).
   - optional `COMICS_REPO_URL`, falls ansible-pull nicht aus diesem GitHub-Repo ziehen soll.
2. Tag setzen: `git tag v1.0.0 && git push origin v1.0.0`. Die Action `build-iso` baut die ISO
   und hängt sie als Teile (`*.iso.part-00`, `-01`, …) plus `.sha256` an den Release.
   GitHub erlaubt nur 2 GiB pro Datei, die ISO hat etwa 4 GB.

Lokal geht es auch (braucht `xorriso`, `gpg`, `curl`):

```bash
SSH_KEYS_FILE=~/.ssh/id_ed25519.pub REPO_URL=https://github.com/<user>/comic-shop.git os/build-iso.sh
# Ergebnis: os/build/comics-comics-01.iso (+ .sha256)
```

> ansible-pull klont das Repo beim ersten Start **ohne Zugangsdaten**, weil die ISO öffentlich ist
> und keine Token enthalten darf. Empfehlung: Repo öffentlich halten (es enthält keine Geheimnisse).
> Bei privatem Repo nach dem ersten Boot einen Deploy-Key unter `/root/.ssh/` hinterlegen,
> `REPO_URL` in `/etc/comics/repo.conf` auf die SSH-URL ändern und `sudo comics-update` ausführen.

## Laptop als Rechner (ADR-0029)

- Erster Lauf von ansible-pull braucht **Kabel-LAN** (Adapter reicht). WLAN als Fallback: `WIFI_SSID` und
  `WIFI_PASSWORD` in `/etc/comics/comics.env`, dann `sudo comics-update --tags laptop`.
- Deckel zuklappen ist erlaubt, der Rechner schläft nicht. BIOS: „Power on after AC loss“ falls vorhanden,
  Ladelimit 80 %.
- Scanner ist per Standard aus (`comics_scanner_enabled: false`); Eingang per Foto-Upload.

## 1. ISO herunterladen und prüfen

```bash
cat comics-comics-01.iso.part-* > comics-comics-01.iso
sha256sum -c comics-comics-01.iso.sha256
```

## 2. USB-Stick beschreiben

balenaEtcher oder unter Linux:

```bash
lsblk                                   # Stick identifizieren!
sudo dd if=comics-comics-01.iso of=/dev/sdX bs=4M status=progress conv=fsync
```

## 3. BIOS/UEFI einstellen (manuell)

- Boot von USB erlauben, Stick als erstes Boot-Gerät (oder Boot-Menü per F12/F8/Esc).
- **„Power on after AC loss“ / „Restore on AC Power Loss“ = On.**
- SATA-Modus AHCI. Secure Boot darf an bleiben (Ubuntu ist signiert).
- Optional: Wake-on-LAN an.

## 4. Installation

Vom Stick booten. Der erste Menüpunkt „Comic-Rechner automatisch installieren (LÖSCHT DIE GANZE SSD)“
startet nach 10 Sekunden von selbst. Die Installation läuft ohne Rückfragen durch (ca. 10–20 min)
und startet den Rechner neu. **Stick danach abziehen.**

Achtung: Die größte Festplatte im Rechner wird vollständig gelöscht.

## 5. Erster Start

Der Dienst `comics-firstboot` klont das Repo nach `/opt/comic-shop` und führt `ansible-pull` aus:
Pakete, Firewall, Desktop, Scanner, Sync, K3s. Fortschritt:

```bash
ssh comicadmin@comics-01        # nur per Schlüssel
sudo tail -f /var/log/comics-ansible-pull.log
```

Solange die Geheimnisse fehlen, endet der Lauf mit dem Hinweis, dass die Apps noch nicht ausgerollt sind.
K3s läuft dann bereits.

## 6. Geheimnisse einspielen (manuell)

```bash
sudo install -m 600 /dev/null /etc/comics/comics.env   # existiert bereits mit Rechten 600
sudo nano /etc/comics/comics.env                       # Inhalt aus dem Passwort-Manager
sudo comics-update                                     # ansible-pull erneut, rollt die Apps aus
```

Format wie `.env.example`: `NAME=wert`, ohne Anführungszeichen, eine Variable pro Zeile.
Werte für einen neuen Bucket liefert `terraform output` in `infra/aws` (siehe `infra/aws/README.md`).

**`N8N_ENCRYPTION_KEY` muss bei einer Neuinstallation derselbe sein wie vorher**, sonst sind alle
in n8n gespeicherten Credentials unbrauchbar. Er steht im Passwort-Manager.

Alternative SOPS/age: `comics.env.sops` im Repo, privater age-Schlüssel nur unter
`/etc/comics/age.key` und im Passwort-Manager. Entschlüsseln mit
`sudo SOPS_AGE_KEY_FILE=/etc/comics/age.key sops -d /opt/comic-shop/os/comics.env.sops > /etc/comics/comics.env`.

## 7. Prüfen

```bash
sudo /opt/comic-shop/scripts/verify.sh            # mit Probe-Scan (Scanner angeschlossen, Vorlage eingelegt)
sudo /opt/comic-shop/scripts/verify.sh --skip-scan
```

Danach n8n im Browser öffnen: `https://comics-01/` (selbstsigniertes Zertifikat im LAN),
Owner-Konto anlegen, Workflows importieren (`docs/BETRIEB.md` → „Workflows einspielen“).

## Abnahme (Phase 2)

| Test | Vorgehen | Erwartung |
| --- | --- | --- |
| Komplettinstallation | Stoppuhr ab Schritt 4 | < 60 min bis grünes `verify.sh` |
| Stromausfall | Netzstecker ziehen, nach 1 min einstecken | Rechner startet allein, `verify.sh --skip-scan` grün, Workflows vorhanden |
| Reproduzierbarkeit | Schritte 1–7 auf demselben Rechner wiederholen | gleiches Ergebnis |
| Scanner | `comics-probe-scan` mit echtem Gerät | 2-seitige PDF |

## Konfiguration später ändern

Alles über das Repo: Änderung committen und pushen, dann auf dem Rechner `sudo comics-update`.
Einzelne Rollen: `sudo comics-update --tags apps`.
