# CLAUDE.md – Konventionen für dieses Repo

Comic-Shop-Automatisierung: Scan → S3 → Erkennung (Claude) → Review → Shopify → Verkauf.
Architektur: `docs/ARCHITEKTUR.md`. Umsetzungsplan und Status: `docs/PLAN.md`.

## Regeln

- **Keine Secrets im Repo.** Weder AWS-Keys, Shopify-/Ximilar-/Anthropic-Token, `N8N_ENCRYPTION_KEY`
  noch Passwörter. Neue Variablen immer in `.env.example` (ohne Wert) eintragen.
  Geheimnisse liegen auf dem Rechner in `/etc/comics/comics.env` (Rechte 600) oder SOPS-verschlüsselt.
- **n8n-Workflows nach jeder Änderung exportieren und committen**
  (`scripts/n8n-export.sh`). Exporte ohne Credentials (`--decrypted` niemals verwenden).
- **Sprache:** Doku, Commit-Messages und UI-Texte deutsch. Code-Kommentare, Bezeichner und Logs englisch.
- Nach jeder Plan-Phase committen, Status in `docs/PLAN.md` nachziehen.
- Zentrale Geschäftswerte (Zustandsfaktoren, Aufschlag, Rundung, Konfidenzschwelle) stehen nur in
  `config/pricing.yaml` – nirgends sonst hart codieren.
- Comicguide: kein Scraping, keine Übernahme von Texten oder Bildern (siehe `docs/PREISFINDUNG.md`).

## Aufbau

```
os/                 Autoinstall-ISO, Ansible-Rollen (ansible-pull)
infra/k3s/          Kubernetes-Manifeste (Kustomize), Namespace comics
infra/aws/          Terraform für S3-Bucket und IAM
services/comic-helper/  Python-Dienst (FastAPI): S3, PDF→Bild, Claude, Preise, Shopify, Review-UI
workflows/          exportierte n8n-Workflows (JSON)
scripts/            Hilfsskripte (verify.sh, n8n-export.sh, Vergleichstest)
config/             fachliche Konfiguration (pricing.yaml)
docs/               Architektur, Betrieb, INSTALL.md
```

## Prüfen vor dem Commit

```bash
cd services/comic-helper && python -m pytest -q      # Unit-Tests (S3 via moto)
kubectl kustomize infra/k3s >/dev/null                # Manifeste rendern
terraform -chdir=infra/aws validate                   # falls terraform installiert
bash -n os/build-iso.sh scripts/*.sh
```
