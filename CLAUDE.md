# CLAUDE.md – Konventionen für dieses Repo

Comic-Shop-Automatisierung: Scan → S3 → Erkennung (Claude) → Review → Shopify → Verkauf.

## Grundlage: Architecture Decision Records

**Die ADRs in `docs/adr/` sind die verbindliche Grundlage für jede Arbeit in diesem Repo.**
Übersicht und Status: `docs/adr/README.md`.

1. Vor jeder Änderung an Architektur, Datenhaltung, Sicherheit, Infrastruktur oder Fachlogik die
   betroffenen ADRs lesen. Code, Konfiguration, Workflows und Doku müssen den akzeptierten ADRs entsprechen.
2. Widerspricht eine Aufgabe einem akzeptierten ADR, nicht stillschweigend abweichen: den Konflikt
   benennen und das ADR ändern lassen. Ein ADR beschreibt den **aktuellen Stand** und wird angepasst
   (Verlauf steht in Git); nur ein ganz anderes Thema bekommt ein neues ADR (`docs/adr/_vorlage.md`).
3. Nur tragende Entscheidungen bekommen ein ADR (schwer rückgängig, nicht aus dem Code ablesbar, echte
   Alternativen). Vorher prüfen, ob ein bestehendes ADR sie aufnehmen kann. Funktionen der Oberfläche,
   Konfigurationswerte und Betriebsschritte gehören in die Doku, nicht in ein ADR (siehe ADR-0000).
   Das ADR kommt im selben Commit wie die Umsetzung; Übersicht in `docs/adr/README.md`.
4. ADRs mit Status `Vorgeschlagen` (0010 Erkennung) gelten vorläufig; bei Klärung auf `Akzeptiert` setzen.
5. In Commit-Messages und PRs die betroffenen ADRs nennen (z. B. „gemäß ADR-0004“).

Weitere Doku: `docs/ARCHITEKTUR.md` (Datenfluss, Zustände), `docs/PLAN.md` (Plan und Status).
`future-improvements/` enthält nur Ideen und Ausbaupläne; daraus wird erst nach einem akzeptierten ADR umgesetzt.

## Sandbox zuerst (ADR-0027)

Jede Änderung an comic-helper, Workflows und `config/pricing.yaml` wird zuerst in der Sandbox auf dem MacBook
(OrbStack, Docker Compose) ausgerollt und dort geprüft (`docs/SANDBOX-MAC.md`: `scripts/sandbox-orbstack.sh up`,
geänderte Workflows per `import`), erst danach auf dem Comic-Rechner (`sudo comics-update`). Änderungen an
`infra/k3s/` und `os/` lassen sich dort nicht prüfen (kein K3s): rendern und zuerst auf dem Comic-Rechner beobachten.
Die Sandbox nutzt nie Produktivdaten.

Rollout auf den Comic-Rechner vom Mac aus (ADR-0027): erst Merge nach `main` (der Rechner zieht `main`), dann
`ssh -i ~/.ssh/id_ed25519_comics comicadmin@192.168.40.120 'sudo comics-update --tags apps'`.

## Regeln

- **Keine Secrets im Repo** (ADR-0003). Weder AWS-Keys, Shopify-/Ximilar-/Anthropic-Token, `N8N_ENCRYPTION_KEY`
  noch Passwörter. Neue Variablen immer in `.env.example` (ohne Wert) eintragen.
  Geheimnisse liegen auf dem Rechner in `/etc/comics/comics.env` (Rechte 600) oder SOPS-verschlüsselt.
- **n8n-Workflows nach jeder Änderung exportieren und committen**
  (`scripts/n8n-export.sh`). Exporte ohne Credentials (`--decrypted` niemals verwenden).
- **Sprache:** Doku, Commit-Messages und UI-Texte deutsch. Code-Kommentare, Bezeichner und Logs englisch.
- Nach jeder Plan-Phase committen, Status in `docs/PLAN.md` nachziehen.
- Zentrale Geschäftswerte (Zustandsfaktoren, Aufschlag, Rundung, Konfidenzschwelle) stehen nur in
  `config/pricing.yaml` – nirgends sonst hart codieren (ADR-0011).
- Comicguide: kein Scraping, keine Übernahme von Texten oder Bildern (ADR-0011).

## Aufbau

```
os/                 Autoinstall-ISO, Ansible-Rollen (ansible-pull)
infra/k3s/          Kubernetes-Manifeste (Kustomize), Namespace comics
infra/sandbox-orbstack/  Docker-Compose-Sandbox für das MacBook (ADR-0027)
infra/aws/          Terraform für S3-Bucket und IAM
services/comic-helper/  Python-Dienst (FastAPI): S3, PDF→Bild, Claude, Preise, Shopify, Review-UI
workflows/          exportierte n8n-Workflows (JSON)
scripts/            Hilfsskripte (verify.sh, n8n-export.sh, Vergleichstest)
config/             fachliche Konfiguration (pricing.yaml)
docs/               ADRs (docs/adr/), Architektur, Betrieb, INSTALL.md
hardware/           Hardware-Empfehlung und Linux-Kompatibilität (aktueller Ausbau)
future-improvements/  Spätere Ausbaustufen, nicht verbindlich bis als ADR akzeptiert
```

## Prüfen vor dem Commit

```bash
cd services/comic-helper && python -m pytest -q      # Unit-Tests (S3 via moto)
kubectl kustomize infra/k3s >/dev/null                # Manifeste rendern
terraform -chdir=infra/aws validate                   # falls terraform installiert
bash -n os/build-iso.sh scripts/*.sh
```
