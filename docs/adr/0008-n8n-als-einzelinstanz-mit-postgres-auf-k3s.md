# ADR-0008: n8n als Einzelinstanz mit Postgres auf K3s

- **Status:** Akzeptiert
- **Datum:** 2026-10-27

## Kontext
Plan 3: ca. 2.000 Scans pro Monat. n8n braucht eine persistente Datenbank.

## Entscheidung
- K3s (gepinnt), Namespace `comics`, local-path-Storage.
- Postgres als StatefulSet nur für n8n; n8n als Deployment mit `replicas: 1`, Strategie `Recreate`.
- Kein Queue-Mode.
- Traefik-Ingress: `/` → n8n, `/review` → comic-helper; Ports 80/443 nur aus dem LAN.
- Tägliches Backup (`pg_dump` + Workflow-Export nach S3); Workflows zusätzlich im Repo.

## Konsequenzen
- Kurze Ausfallzeit bei Updates/Neustarts (akzeptiert, da Polling und Retries nachholen).
- Workflows müssen nach jeder Änderung exportiert und committet werden.

## Verworfene Alternativen
- Queue-Mode mit Redis und Workern (unnötig bei dieser Last).

## Bezug
Plan 3; `infra/k3s/`
