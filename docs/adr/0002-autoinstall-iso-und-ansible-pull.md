# ADR-0002: Reproduzierbare Installation: Autoinstall-ISO und ansible-pull

- **Status:** Akzeptiert
- **Datum:** 2026-10-27, konsolidiert 2026-11-13 (enthält frühere ADR-0015, ADR-0031)

## Kontext
Der Rechner muss im Notfall in unter einer Stunde neu aufgesetzt werden können. Die Hardware ist alt und
nicht einheitlich.

## Entscheidung
- Ubuntu Server 24.04 LTS. Die offizielle ISO wird per `os/build-iso.sh` um eine Autoinstall-Konfiguration
  ergänzt (Prüfsumme und GPG-Signatur werden verifiziert). Pakete werden bei der Installation geladen.
- Beim ersten Start klont `comics-firstboot` das Repo und führt `ansible-pull` aus. Spätere Änderungen:
  `sudo comics-update`. **Das Repo (Branch `main`) ist die einzige Quelle der Konfiguration.**
- Versionen (K3s, n8n, Postgres, NAPS2, Python-Pakete) sind fest gepinnt.
- **ISO-Verteilung:** GitHub Actions baut bei Release-Tags `v*` und lädt die ISO in Teilen (je < 2 GiB, GitHub-Limit)
  plus Prüfsumme hoch. Der lokale Bau bleibt gleichwertig. Admin-SSH-Schlüssel (öffentlich) kommen aus der
  Repo-Variable `ADMIN_SSH_KEYS`.
- **Netzboot als einmalige Alternative zum USB-Stick:** `scripts/netboot.sh` bietet dieselbe ISO per UEFI-Netzboot an
  (dnsmasq als proxyDHCP + TFTP, ISO per HTTP). Der Router-DHCP bleibt unverändert. Das Bootmenü hat keinen Timeout.

## Konsequenzen
- Keine Handarbeit auf dem Rechner außer BIOS und Geheimnissen. Was nicht im Repo steht, existiert nicht.
- Die größte Platte wird ohne Rückfrage gelöscht (deutlicher Bootmenü-Eintrag).
- `ansible-pull` braucht Lesezugriff aufs Repo ohne Zugangsdaten in der ISO (ADR-0003).
- Netzboot lädt die ISO (ca. 4 GB) in den RAM: mindestens 8 GB, Kabel-LAN, UEFI mit Netzwerkboot.

## Verworfene Alternativen
- Vorgebackenes Disk-Image mit Packer (fragil bei unterschiedlicher alter Hardware).
- ISO in S3 ablegen (bräuchte AWS-Zugang in der CI); Router-DHCP für PXE ändern (Eingriff ins Heimnetz).

## Bezug
`os/`, `.github/workflows/build-iso.yml`, `scripts/netboot.sh`, `docs/INSTALL.md`
