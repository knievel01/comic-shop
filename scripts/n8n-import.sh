#!/usr/bin/env bash
# Imports all workflows from workflows/ into the running n8n (fresh install or restore).
# Credentials are NOT part of the repo: create them once in the n8n UI with the names
# listed in docs/BETRIEB.md ("n8n-Credentials"), then activate the workflows.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
KC=(k3s kubectl -n comics)
command -v k3s >/dev/null || KC=(kubectl -n comics)

tar -C "$REPO/workflows" -cf - --exclude='README.md' . \
  | "${KC[@]}" exec -i deploy/n8n -- sh -c 'rm -rf /tmp/wf-in && mkdir -p /tmp/wf-in && tar -C /tmp/wf-in -xf -'
"${KC[@]}" exec deploy/n8n -- n8n import:workflow --separate --input=/tmp/wf-in/
echo "Import fertig. Credentials prüfen und Workflows in der UI aktivieren."
