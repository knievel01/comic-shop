# ADR-0027: Der PoC bleibt als Sandbox, Änderungen laufen zuerst dort

- **Status:** Akzeptiert, Standort in Teilen ersetzt durch ADR-0039
- **Datum:** 2026-11-05
- **Ergänzt:** ADR-0002 (Installation per ISO und ansible-pull), `docs/POC.md`

## Kontext
Der Machbarkeits-PoC auf dem vorhandenen K3s des Entwickler-Rechners `pro-mini` (`docs/POC.md`) war
als vorübergehende Testumgebung ohne ADR gedacht und sollte nach dem Go-Live abgebaut werden. Er hat sich
aber bewährt: Er ist schnell neu gebaut, vom Handy im WLAN erreichbar und arbeitet mit einem
Shopify-Entwicklungsshop. Laut `docs/POC.md` braucht ein dauerhafter Betrieb des PoC ein eigenes ADR.

## Entscheidung
- Der PoC bleibt dauerhaft als **Sandbox** auf `pro-mini` bestehen (`infra/k3s-poc/`,
  `scripts/poc-host-k3s.sh`, `http://pro-mini.fritz.box/`). Er wird nach dem Go-Live nicht abgebaut.
- **Jede Änderung** an comic-helper, Workflows, Manifesten oder `config/pricing.yaml` wird zuerst in der
  Sandbox ausgerollt (`scripts/poc-host-k3s.sh build` und `deploy`, Workflows per `n8n-import.sh`) und dort
  geprüft. Erst danach kommt sie auf den Comic-Rechner (`sudo comics-update`).
- Die Sandbox arbeitet nie mit Produktivdaten: eigener S3-Bucket bzw. Präfix, Shopify-Entwicklungsshop,
  eigene Zugangsdaten in `~/.config/comics/comics.env`.
- Die Abweichungen der Sandbox vom Zielaufbau bleiben wie in `docs/POC.md` beschrieben (kein ISO, kein
  Ansible, kein Scanner, nur http). Sie gelten nur für die Sandbox, nicht für den Comic-Rechner.

## Konsequenzen
- Fehler fallen auf, bevor sie den Laden treffen. Neue Funktionen lassen sich vorher auf dem Handy zeigen.
- Zwei Umgebungen zu pflegen: Die Sandbox muss mit dem Repo Schritt halten. Vor jedem Rollout auf den
  Comic-Rechner läuft derselbe Commit in der Sandbox.
- Die Sandbox ist aus dem ganzen WLAN erreichbar, ohne Verschlüsselung (`docs/POC.md`, Abschnitt Zugriff).
- `docs/GO-LIVE.md`: Der Schritt „PoC abbauen“ entfällt, stattdessen wird die Sandbox auf Testdaten umgestellt.

## Verworfene Alternativen
- PoC nach dem Go-Live abbauen (bisheriger Plan): Danach gäbe es keinen Ort zum Testen außer dem Laden selbst.
- Zweiter Namespace auf dem Comic-Rechner: teilt sich Hardware, Firewall und Risiko mit dem Betrieb.

## Bezug
`docs/POC.md`, `docs/GO-LIVE.md`, `infra/k3s-poc/`, `scripts/poc-host-k3s.sh`, `CLAUDE.md`.
