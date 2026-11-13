# ADR-0039: Sandbox auf dem MacBook mit OrbStack und Docker Compose, ohne K3s

- **Status:** Akzeptiert
- **Datum:** 2026-11-13
- **Ersetzt:** ADR-0038
- **Ergänzt:** ADR-0027 (Standort der Sandbox; Grundsatz „Änderungen zuerst in der Sandbox“ bleibt)

## Kontext
ADR-0038 sah K3s in einer Lima-VM auf dem MacBook vor, damit die Sandbox dem Comic-Rechner möglichst
nahekommt. Auf dem Mac läuft aber OrbStack, und der Aufwand für eine zweite VM mit K3s, Registry und
Kubeconfig steht in keinem Verhältnis zum Nutzen für eine Testumgebung. Der Comic-Rechner bleibt K3s
(ADR-0008); der Konflikt gilt nur für die Sandbox, die laut ADR-0027 ohnehin vom Zielaufbau abweichen darf.

## Entscheidung
- Die Sandbox läuft auf dem MacBook als **Docker Compose in OrbStack**: `infra/sandbox-orbstack/compose.yaml`
  mit `postgres`, `n8n` und `comic-helper`, gesteuert über `scripts/sandbox-orbstack.sh`.
- Dieselben Images und Versionen wie in `infra/k3s` (Postgres 17.11-alpine, n8n 2.46.0, comic-helper aus
  `services/comic-helper/Containerfile`), dieselben Dienstnamen. Der Container `comic-helper` trägt zusätzlich den
  Netzwerk-Alias `comic-helper.comics.svc.cluster.local`, damit die exportierten Workflows unverändert bleiben (ADR-0005).
- Kein K3s, kein Traefik, kein Ingress: n8n unter `http://localhost:5678/`, Review-Oberfläche unter
  `http://localhost:8080/review/`. Die Ports sind nur an `127.0.0.1` gebunden, nichts ist im WLAN erreichbar.
- Geheimnisse liegen in `~/.config/comics/comics.env` (Rechte 600, ADR-0003) und kommen nicht ins Repo. Die Sandbox
  nutzt nur Test-Bucket, Entwicklungsshop und eigene Schlüssel (ADR-0027).
- Zugriff vom Handy ist optional und nicht Teil der Entscheidung (siehe `docs/SANDBOX-MAC.md`).

## Konsequenzen
- **Die Sandbox prüft keine Kubernetes-Besonderheiten.** Ingress-Pfade, `securityContext`, Probes, Secret-Einbindung
  und Volumes aus `infra/k3s` laufen dort nicht. Änderungen an `infra/k3s/` und `os/` werden deshalb mit
  `kubectl kustomize infra/k3s` gerendert und beim ersten Rollout bewusst auf dem Comic-Rechner beobachtet.
  Für comic-helper, Workflows und `config/pricing.yaml` gilt ADR-0027 unverändert.
- Die Image-Versionen stehen jetzt an zwei Stellen (`infra/k3s`, Compose-Datei) und müssen gemeinsam geändert werden.
- Images laufen auf einem Apple-Silicon-Mac als `linux/arm64`, der Comic-Rechner läuft auf `amd64`.
- Die Sandbox ist nur verfügbar, solange das MacBook wach ist und OrbStack läuft. Mit `restart: unless-stopped`
  starten die Container nach einem Neustart von OrbStack wieder.
- Der PoC auf `pro-mini` wird abgebaut: `infra/k3s-poc/`, `scripts/poc-host-k3s.sh` und `docs/POC.md` sind aus dem Repo
  entfernt, der Namespace `comics` dort wird gelöscht. Der Comic-Rechner hat seit dem Go-Live (13.11.2026) keine
  Rückfallebene mehr auf `pro-mini`.

## Verworfene Alternativen
- **K3s in einer Lima-VM (ADR-0038):** näher am Comic-Rechner, aber zweite VM, Registry-Weiterleitung und
  Kubeconfig-Pflege für eine Testumgebung.
- **Kubernetes in OrbStack (k8s statt K3s):** hielte `infra/k3s` testbar, bräuchte aber eine Kustomize-Variante
  ohne `local-path` und Traefik. Möglicher Ausbau, falls die Lücke aus den Konsequenzen weh tut.
- **k3d:** gleiche Lücke wie Lima, dazu eine weitere Werkzeugkette neben OrbStack.

## Bezug
`docs/SANDBOX-MAC.md`, `infra/sandbox-orbstack/compose.yaml`, `scripts/sandbox-orbstack.sh`,
ADR-0003, ADR-0005, ADR-0008, ADR-0027, ADR-0038.
