# ADR-0002: Reproduzierbare Installation: Autoinstall-ISO und ansible-pull

- **Status:** Akzeptiert
- **Datum:** 2026-10-27

## Kontext
Der Rechner muss im Notfall in unter einer Stunde neu aufgesetzt werden können (Plan 2.2). Die Hardware
ist alt und nicht einheitlich.

## Entscheidung
- Ubuntu Server 24.04 LTS.
- Weg A: Die offizielle ISO wird per `os/build-iso.sh` um eine Autoinstall-Konfiguration ergänzt
  (Prüfsumme und GPG-Signatur werden verifiziert). Pakete werden bei der Installation geladen.
- Beim ersten Start klont `comics-firstboot` das Repo und führt `ansible-pull` aus.
  Spätere Änderungen: `sudo comics-update`. Das Repo ist die einzige Quelle der Konfiguration.
- Versionen (K3s, n8n, Postgres, NAPS2, Python-Pakete) sind fest gepinnt.

## Konsequenzen
- Keine Handarbeit auf dem Rechner außer BIOS und Geheimnissen. Was nicht im Repo steht, existiert nicht.
- Die größte Platte wird ohne Rückfrage gelöscht (deutlicher Bootmenü-Eintrag, 10 s Wartezeit).
- ansible-pull braucht Lesezugriff aufs Repo ohne Zugangsdaten in der ISO (siehe ADR-0003, ADR-0015).

## Verworfene Alternativen
- Weg B: Vorgebackenes Disk-Image mit Packer (fragil bei unterschiedlicher alter Hardware).

## Bezug
Plan 2.2–2.5; `os/`, `docs/INSTALL.md`
