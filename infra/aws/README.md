# AWS: S3-Bucket und IAM (Phase 4)

Legt an:

- Bucket in `eu-central-1`: Public Access komplett blockiert, Versioning an, SSE-S3, nur HTTPS.
- Lifecycle: alte Objektversionen nach 30 Tagen löschen, `backup/` nach 90 Tagen,
  Reste von `verify.sh` nach 1 Tag.
- IAM-User `comics-app` (n8n, comic-helper, Backup): List/Get/Put/Delete und Tagging, nur auf diesem Bucket.
- IAM-User `comics-scan-upload` (Scan-Station): nur `PutObject` unter `eingang/`.
  Ein gestohlener Scan-Rechner kann also nichts lesen oder löschen.

Präfixe (entstehen von selbst):

```
eingang/     frisch gescannte PDFs (+ KI-Vorschlag als <id>.ki.json), Status als Objekt-Tag
aktiv/       bestätigt und in Shopify angelegt
verkauft/    verkaufte Exemplare
backup/      pg_dump und Workflow-Export (Rolle backup)
```

## Anlegen

Mit einem Admin-Profil (nicht mit den hier erzeugten Schlüsseln):

```bash
cd infra/aws
cp terraform.tfvars.example terraform.tfvars      # Bucket-Namen eintragen
terraform init
terraform apply
terraform output -raw comics_env                  # -> in den Passwort-Manager und nach /etc/comics/comics.env
```

`terraform.tfstate` enthält die geheimen Schlüssel. Er wird nicht committet. Am besten liegt er
verschlüsselt im Passwort-Manager-Tresor oder in einem S3-Backend in einem separaten Admin-Konto.

## Abnahme

```bash
# Test-Upload mit dem Scan-Schlüssel klappt
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... aws s3 cp test.txt s3://<bucket>/eingang/_verify/test.txt
# Lesen mit dem Scan-Schlüssel scheitert (AccessDenied)
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... aws s3 ls s3://<bucket>/
# Zugriff ohne Credentials scheitert (403)
curl -s -o /dev/null -w '%{http_code}\n' https://<bucket>.s3.eu-central-1.amazonaws.com/eingang/_verify/test.txt
```

`scripts/verify.sh` prüft dasselbe auf dem Comic-Rechner automatisch.
