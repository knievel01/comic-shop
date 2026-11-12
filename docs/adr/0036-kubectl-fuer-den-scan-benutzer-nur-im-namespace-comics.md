# ADR-0036: kubectl für den Scan-Benutzer nur im Namespace comics

- **Status:** Akzeptiert
- **Datum:** 2026-11-12

## Kontext
Der Benutzer `scan` ist das Stations-Konto mit Autologin (ADR-0001, ADR-0032). Für Logs und Neustarts der Dienste soll er
`kubectl` nutzen können. Für `comicadmin` kopiert die Rolle `k3s` die Cluster-Admin-Kubeconfig (ADR-0008); dasselbe für
`scan` würde jedem am Gerät volle Rechte im ganzen Cluster geben.

## Entscheidung
- ServiceAccount `scan-operator` im Namespace `comics` mit RoleBinding auf die eingebaute ClusterRole `admin`
  (gilt nur im Namespace). Manifest: `infra/k3s/base/operator-rbac.yaml`.
- Die Rolle `apps` schreibt daraus `/home/scan/.kube/config` (Rechte 600, Server `https://127.0.0.1:6443`, Standard-Namespace
  `comics`); `/etc/profile.d/comics-kube.sh` setzt `KUBECONFIG` für `scan`.
- Keine Rechte auf Nodes, andere Namespaces oder Cluster-Ressourcen.

## Konsequenzen
- `scan` kann im Namespace `comics` Pods, Logs, Neustarts, `exec` und auch dessen Secrets (z. B. `comics-env`) lesen.
  Das ist für den Betrieb nötig, bedeutet aber: wer am Gerät als `scan` sitzt, kann an die Anwendungsgeheimnisse.
- Das Token liegt dauerhaft im Secret `scan-operator-token`; Widerruf: Secret oder ServiceAccount löschen und
  `sudo comics-update --tags apps` ausführen.

## Verworfene Alternativen
- Admin-Kubeconfig kopieren – Cluster-Admin für das Stations-Konto.
- Nur `view` – reicht nicht für Neustarts und `exec`.

## Bezug
ADR-0001, ADR-0008, ADR-0032; `infra/k3s/base/operator-rbac.yaml`, `os/ansible/roles/apps`
