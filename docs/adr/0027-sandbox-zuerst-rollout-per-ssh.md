# ADR-0027: Sandbox zuerst, dann Rollout per SSH; Sandbox und Produktion teilen keine Daten

- **Status:** Akzeptiert
- **Datum:** 2026-11-05, konsolidiert 2026-11-13 (enthält frühere ADR-0033, ADR-0035, ADR-0038, ADR-0039, ADR-0040)

## Kontext
Der Machbarkeits-PoC hat sich bewährt und sollte nicht abgebaut werden; jede Änderung soll erst getestet werden, bevor
sie den Laden trifft. Die Sandbox lief zunächst auf `pro-mini` (K3s), dann kurz in einer Lima-VM, jetzt auf dem MacBook.
Der Comic-Rechner holt seinen Stand per `ansible-pull` aus `main` (ADR-0002); der Entwicklungsrechner soll das auslösen können.

## Entscheidung
- **Sandbox:** Docker Compose in OrbStack auf dem MacBook (`infra/sandbox-orbstack/compose.yaml`, `scripts/sandbox-orbstack.sh`)
  mit `postgres`, `n8n`, `comic-helper`, denselben Images und Versionen wie `infra/k3s`, Ports nur an `127.0.0.1`.
  Kein K3s, kein Traefik. Der comic-helper trägt den Alias `comic-helper.comics.svc.cluster.local`, damit die Workflows
  unverändert laufen (ADR-0005).
- **Reihenfolge:** Jede Änderung an comic-helper, Workflows und `config/pricing.yaml` zuerst in der Sandbox prüfen, dann
  nach `main` mergen, dann auf dem Comic-Rechner ausrollen. Änderungen an `infra/k3s/` und `os/` lassen sich in der
  Sandbox nicht prüfen: mit `kubectl kustomize` rendern und beim ersten Rollout beobachten.
- **Keine gemeinsamen Daten:** Die Sandbox nutzt nie Produktivdaten (eigener Test-Bucket, Entwicklungsshop, eigene
  Schlüssel in `~/.config/comics/comics.env`). Produktion hat einen eigenen Bucket per Terraform (`infra/aws`,
  Bucket `comics-scans-roman-prod-0001`, IAM-User `comics-prod-*` über `name_prefix`); Terraform-State bleibt lokal,
  nicht im Git, und wird im Passwort-Manager gesichert.
- **Rollout per SSH:** Vom Entwicklungsrechner (auch durch Claude Code im Auftrag des Nutzers):
  `ssh -i ~/.ssh/id_ed25519_comics comicadmin@192.168.40.120 'sudo comics-update --tags apps'`. Ohne `--tags apps`
  (z. B. `os/`-Rollen) nur nach ausdrücklicher Freigabe. Erlaubt sind außerdem lesende Prüfungen. Direkte Änderungen am
  Rechner sind kein Weg; das Repo bleibt die Quelle. Der private Schlüssel bleibt auf dem Entwicklungsrechner (ADR-0003).

## Konsequenzen
- Fehler fallen auf, bevor sie den Laden treffen. Die Sandbox prüft keine Kubernetes-Besonderheiten (Ingress, Probes,
  `securityContext`, Volumes); Image-Versionen stehen an zwei Stellen und müssen gemeinsam geändert werden.
- Images laufen auf dem Mac als `arm64`, der Comic-Rechner ist `amd64`. Die Sandbox ist nur verfügbar, solange das
  MacBook wach ist und OrbStack läuft.
- Es gibt keine Rückfallebene für die Verarbeitung auf einem zweiten Rechner (`pro-mini` ist abgebaut).
- Wer den SSH-Schlüssel hat, hat wegen `sudo` ohne Passwort Root auf dem Comic-Rechner: Schlüssel in Schlüsselbund bzw.
  SSH-Agent, Mac gesperrt halten. Die LAN-Adresse kann sich ändern (DHCP); dann hier anpassen oder feste Adresse vergeben.
- Shopify-App und Anthropic-Konto sind für Sandbox und Produktion noch gemeinsam; sind beide Systeme aktiv, schreiben
  beide Entwürfe in denselben Shop. Ein eigener Dev-Shop für die Sandbox steht aus.

## Verworfene Alternativen
- PoC nach dem Go-Live abbauen (kein Testort außer dem Laden); zweiter Namespace auf dem Comic-Rechner (teilt Risiko).
- K3s in Lima, k3d oder Kubernetes in OrbStack (zweite VM, Registry, Kubeconfig-Pflege für eine Testumgebung; als Ausbau
  denkbar, falls die Lücke zu Kubernetes weh tut).
- Go-Live mit dem PoC-Bucket (vermischt Testdaten und Produktion, nur kurz als Übergang genutzt).
- Rollout nur direkt am Rechner; `sudo` auf `comics-update` beschränken (wäre sauberer, ändert die Rolle `os/ansible`).

## Bezug
`docs/SANDBOX-MAC.md`, `docs/INSTALL.md`, `docs/BETRIEB.md`, `docs/GO-LIVE.md`, `infra/aws`, `CLAUDE.md`
