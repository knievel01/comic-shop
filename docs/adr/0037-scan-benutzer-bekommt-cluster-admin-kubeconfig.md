# ADR-0037: Scan-Benutzer bekommt die Cluster-Admin-Kubeconfig

- **Status:** Akzeptiert
- **Datum:** 2026-11-12
- **Ersetzt:** ADR-0036

## Kontext
ADR-0036 begrenzte `kubectl` für den Benutzer `scan` auf den Namespace `comics`. Der Betreiber will für `scan` vollen Zugriff,
wie für `comicadmin`: das Stations-Konto soll den Cluster ohne Einschränkung verwalten können.

## Entscheidung
- Die Rolle `k3s` kopiert `/etc/rancher/k3s/k3s.yaml` nach `/home/scan/.kube/config` (Besitzer `scan`, Rechte 600),
  wie schon für `comics_admin_user`. `KUBECONFIG` für `scan` zeigt darauf (`/etc/profile.d/comics-kube.sh`).
- ServiceAccount, Token-Secret und RoleBinding aus ADR-0036 entfallen (`infra/k3s/base/operator-rbac.yaml` ist weg,
  die Objekte im Cluster werden gelöscht).

## Konsequenzen
- Wer am Gerät als `scan` angemeldet ist (Autologin, ADR-0001/0032), hat Cluster-Admin: alle Namespaces, Nodes, Secrets.
  Das Konto hat kein sudo, `kubectl` reicht aber, um Pods mit Host-Zugriff zu starten und damit Root-Rechte auf dem
  Rechner zu erlangen. Die physische Anmeldung am Laptop ist damit der Vertrauensanker.
- Die Kubeconfig enthält ein Client-Zertifikat von K3s; bei Zertifikatserneuerung `sudo comics-update --tags k3s`.
- Einschränken lässt sich das später wieder per neuem ADR (z. B. ADR-0036 reaktivieren).

## Verworfene Alternativen
- Zugriff nur im Namespace `comics` (ADR-0036) – vom Betreiber nicht gewünscht.

## Bezug
ADR-0001, ADR-0008, ADR-0032, ADR-0036; `os/ansible/roles/k3s`
