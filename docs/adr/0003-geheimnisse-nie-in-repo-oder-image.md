# ADR-0003: Geheimnisse nie in Repo oder Image

- **Status:** Akzeptiert
- **Datum:** 2026-10-27

## Kontext
Die ISO ist ein öffentlich ladbares Artefakt, das Repo kann öffentlich werden (ADR-0002).

## Entscheidung
- Keine Schlüssel, Token, Passwörter oder `N8N_ENCRYPTION_KEY` in Git, ISO oder Container-Image.
- Geheimnisse liegen in `/etc/comics/comics.env` (root, 0600) und im Passwort-Manager; alternativ
  SOPS/age-verschlüsselt im Repo. Ansible erzeugt daraus die Kubernetes-Secrets.
- `.env.example` listet jede Variable ohne Wert. Neue Variablen kommen dort zuerst hinein.
- n8n-Exporte nie mit `--decrypted`.
- Getrennte IAM-Nutzer: `comics-app` (Bucket) und `comics-scan-upload` (nur `PutObject` auf `eingang/`).

## Konsequenzen
- Nach jeder Neuinstallation ein manueller Schritt (Geheimnisse einspielen).
- `N8N_ENCRYPTION_KEY` muss separat gesichert sein, sonst sind n8n-Credentials nach Datenverlust wertlos.
- `terraform.tfstate` enthält Schlüssel und gehört nicht ins Repo.

## Verworfene Alternativen
- Secrets als GitHub-Secrets in die ISO backen (ISO wäre geheim, Verteilung schwieriger).

## Bezug
Plan 2.4; `.gitignore`, `.env.example`, Rolle `apps`, `infra/aws/iam.tf`
