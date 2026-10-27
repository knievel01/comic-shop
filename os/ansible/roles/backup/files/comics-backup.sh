#!/usr/bin/env bash
# Daily backup: n8n Postgres dump + workflow export -> s3://$S3_BUCKET/backup/<date>/
# Restore: docs/BETRIEB.md
set -euo pipefail
: "${S3_BUCKET:?}"
NS=comics
STAMP="$(date +%F)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
kc() { k3s kubectl -n "$NS" "$@"; }

echo "pg_dump ..."
kc exec statefulset/postgres -- sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$TMP/n8n.dump"
[[ -s "$TMP/n8n.dump" ]] || { echo "empty dump" >&2; exit 1; }

echo "n8n workflow export ..."
kc exec deployment/n8n -- sh -c 'rm -rf /tmp/wf && n8n export:workflow --all --separate --output=/tmp/wf >/dev/null && tar -C /tmp -cf - wf' \
  > "$TMP/workflows.tar"

aws s3 cp --only-show-errors "$TMP/n8n.dump" "s3://$S3_BUCKET/backup/$STAMP/n8n.dump"
aws s3 cp --only-show-errors "$TMP/workflows.tar" "s3://$S3_BUCKET/backup/$STAMP/workflows.tar"
echo "backup $STAMP ok"
