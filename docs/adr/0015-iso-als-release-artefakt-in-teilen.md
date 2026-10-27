# ADR-0015: ISO als Release-Artefakt in Teilen

- **Status:** Akzeptiert
- **Datum:** 2026-10-27

## Kontext
Die ISO wird in GitHub Actions gebaut (Plan 2.2). Sie ist ca. 4 GB groß, GitHub erlaubt max. 2 GiB je Release-Datei.

## Entscheidung
- Build bei Release-Tags `v*`; Upload als Teile (`split -b 1900M`) plus `.sha256` der ganzen ISO.
- Admin-SSH-Schlüssel kommen aus der Repo-Variable `ADMIN_SSH_KEYS` (öffentliche Schlüssel, kein Secret).
- Lokaler Bau mit `os/build-iso.sh` bleibt gleichwertig.

## Konsequenzen
- Vor dem Beschreiben des Sticks müssen die Teile zusammengesetzt werden (`docs/INSTALL.md`).

## Verworfene Alternativen
- ISO in S3 ablegen (bräuchte AWS-Zugang in der CI); nur lokaler Bau.

## Bezug
Plan 2.2; `.github/workflows/build-iso.yml`
