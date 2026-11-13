# ADR-0038: Sandbox auf dem MacBook, K3s in einer Lima-VM

- **Status:** Ersetzt durch ADR-0039
- **Datum:** 2026-11-13
- **Ergänzt:** ADR-0027 (Standort der Sandbox; Grundsatz „Änderungen zuerst in der Sandbox“ bleibt)

## Kontext
ADR-0027 legt die Sandbox auf dem Entwickler-Rechner `pro-mini` fest. Sie soll auf dem MacBook laufen,
weil dort die Entwicklung stattfindet und die Sandbox dann ohne zweiten Rechner erreichbar ist.
macOS kann kein K3s nativ betreiben, und der Comic-Rechner ist Linux (ADR-0029). Die Sandbox soll
dem Comic-Rechner so nah wie möglich sein, damit ein Test in der Sandbox etwas über den Laden aussagt.
Das MacBook schläft, wenn man es zuklappt; die Sandbox ist dann nicht erreichbar.

## Entscheidung
- Die Sandbox läuft in einer **Lima-VM** (Ubuntu LTS, `vz`) auf dem MacBook. Darin installiert sich
  **K3s** mit Traefik und local-path, in derselben Version wie auf dem Comic-Rechner (`docs/INSTALL.md`).
- Die Manifeste aus `infra/k3s-poc/` (Registry, Ingress-Overlay, Tailscale) bleiben die Grundlage.
  Die Registry läuft wie bisher in der VM auf `127.0.0.1:5000`; Lima leitet den Port auf den Mac weiter,
  Images werden auf dem Mac gebaut und dorthin gepusht.
- Der Zugriff von außen läuft über **Tailscale** (Operator im Cluster, `infra/k3s-poc/tailscale.yaml`),
  nicht über das LAN. Der Ingress liefert lokal auf `http://localhost:8080/`.
- Die Geheimnisdatei liegt auf dem Mac unter `~/.config/comics/comics.env` (Rechte 600), wie in ADR-0027.
  Die Sandbox nutzt nur Test-Bucket, Entwicklungsshop und eigene Schlüssel (ADR-0003, ADR-0027).
- Der Standort `pro-mini` entfällt für die Sandbox. Der Grundsatz aus ADR-0027 (jede Änderung zuerst in der
  Sandbox, nie mit Produktivdaten) gilt unverändert.

## Konsequenzen
- Gewählt wurden die Empfehlungen aus dem Plan: Lima statt k3d; als Docker-Daemon auf dem Mac Colima im
  Docker-Modus (ohne Kubernetes) oder Docker Desktop, beides erlaubt.
- Die Sandbox ist nur verfügbar, solange das MacBook wach ist und die VM läuft. Der Mac darf während
  eines Tests nicht schlafen (`caffeinate` oder Energieeinstellung).
- Images werden auf einem Apple-Silicon-Mac als `linux/arm64` gebaut, der Comic-Rechner läuft auf
  `amd64`. Der Quellcode ist derselbe, die Binärdateien sind es nicht. Das wird in `docs/POC.md` vermerkt.
- `scripts/poc-host-k3s.sh` war für Linux geschrieben (`stat -c`, `sed -i`, `grep -P`) und läuft jetzt auf beiden
  Systemen. Unter macOS ist das noch ungetestet, siehe `docs/SANDBOX-MAC.md`.
- Der Zugang über Tailscale verschlüsselt den Weg; das Netz ist nicht mehr das ganze WLAN.
  `REVIEW_PASSWORD` bleibt für die Sandbox leer, solange nur das Tailnet darauf zugreift.

## Verworfene Alternativen
- **k3d (K3s in Docker-Containern):** schneller aufgesetzt, aber K3s läuft dort nicht als eigener Knoten
  mit systemd und local-path wie auf dem Comic-Rechner. Fallback, falls Lima Probleme macht.
- **Colima mit Kubernetes:** kombiniert Docker und K3s in einer VM; die Registry-Logik aus `poc-host-k3s.sh`
  müsste dafür neu gebaut werden. Nicht gewählt, weil der Abstand zum Comic-Rechner größer wird.
- **Sandbox bleibt auf `pro-mini`:** Der Rechner ist ein geteilter Entwickler-Rechner mit anderen Diensten
  (ADR-0027). Der Mac soll die Entwicklung und die Sandbox an einem Ort zusammenführen.

## Bezug
`docs/SANDBOX-MAC.md` (Umsetzungsplan), `docs/POC.md`, `infra/k3s-poc/`, `scripts/poc-host-k3s.sh`,
ADR-0027, ADR-0029, ADR-0003.
