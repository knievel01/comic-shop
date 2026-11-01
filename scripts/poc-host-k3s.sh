#!/usr/bin/env bash
# Feasibility PoC: deploys postgres, n8n and comic-helper into an EXISTING K3s
# (e.g. a developer machine) instead of the comic machine. See docs/POC.md.
#
# Usage: scripts/poc-host-k3s.sh env|build|deploy|status|forward|delete
#   env      create the secrets file (internal secrets generated, AWS/Anthropic left empty)
#   build    build the comic-helper image and push it to the PoC registry on localhost:5000
#   deploy   create the Kubernetes secret from the env file and apply infra/k3s-poc
#   status   show pods and volumes
#   forward  port-forward n8n and the review UI to localhost (Ctrl-C to stop)
#   delete   remove the PoC namespace comics including volumes (env file is kept)
#
# Env:
#   COMICS_ENV_FILE  default: ~/.config/comics/comics.env (mode 600, never commit)
#   N8N_PORT         default: 5678
#   HELPER_PORT      default: 8080
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${COMICS_ENV_FILE:-$HOME/.config/comics/comics.env}"
N8N_PORT="${N8N_PORT:-5678}"
HELPER_PORT="${HELPER_PORT:-8080}"
IMAGE=localhost/comic-helper:local
REGISTRY_IMAGE=localhost:5000/comic-helper:local
NS=comics
POC_LABEL=app.kubernetes.io/part-of=comics-poc
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

die() { echo "ERROR: $*" >&2; exit 1; }
env_value() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2-; }

cmd_env() {
  [[ -e "$ENV_FILE" ]] && die "$ENV_FILE exists already (N8N_ENCRYPTION_KEY must stay stable), edit it instead"
  install -d -m 700 "$(dirname "$ENV_FILE")"
  (umask 077 && cp "$ROOT/.env.example" "$ENV_FILE")
  chmod 600 "$ENV_FILE"
  local key
  for key in N8N_ENCRYPTION_KEY POSTGRES_PASSWORD HELPER_TOKEN REVIEW_PASSWORD; do
    sed -i "s|^$key=.*|$key=$(openssl rand -hex 32)|" "$ENV_FILE"
  done
  sed -i -e "s|^WEBHOOK_URL=.*|WEBHOOK_URL=http://localhost:$N8N_PORT/|" \
         -e "s|^REVIEW_BASE_URL=.*|REVIEW_BASE_URL=http://localhost:$HELPER_PORT|" "$ENV_FILE"
  echo "Created $ENV_FILE (mode 600)."
  echo "Fill in at least S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, ANTHROPIC_API_KEY."
  echo "Shopify: use a development store only."
}

cmd_build() {
  # Local registry on 127.0.0.1:5000 (infra/k3s-poc/registry.yaml), no sudo needed.
  kubectl apply -f "$ROOT/infra/k3s/base/namespace.yaml" >/dev/null
  kubectl apply -n "$NS" -f "$ROOT/infra/k3s-poc/registry.yaml"
  kubectl -n "$NS" rollout status deployment/registry --timeout=180s
  docker build -t "$IMAGE" -f "$ROOT/services/comic-helper/Containerfile" "$ROOT"
  docker tag "$IMAGE" "$REGISTRY_IMAGE"
  docker push "$REGISTRY_IMAGE"
  echo "Pushed $REGISTRY_IMAGE. Run '$0 deploy' to (re)start comic-helper."
}

check_env_file() {
  [[ -s "$ENV_FILE" ]] || die "$ENV_FILE missing, run: $0 env"
  (( (8#$(stat -c %a "$ENV_FILE") & 077) == 0 )) || die "$ENV_FILE must not be readable by group/others"
  # Same format rules as the Ansible role apps: NAME=value, no quotes, one per line.
  local bad
  bad="$(grep -nvE '^[[:space:]]*(#.*)?$' "$ENV_FILE" | grep -vE '^[0-9]+:[A-Z_][A-Z0-9_]*=([^"'"'"' ].*)?$' | cut -d: -f1 || true)"
  [[ -z "$bad" ]] || die "invalid lines in $ENV_FILE (NAME=value, no quotes/leading spaces): $(echo $bad)"
  local key
  for key in N8N_ENCRYPTION_KEY POSTGRES_PASSWORD HELPER_TOKEN; do
    [[ -n "$(env_value "$key")" ]] || die "$key is empty in $ENV_FILE"
  done
  for key in S3_BUCKET AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY ANTHROPIC_API_KEY; do
    [[ -n "$(env_value "$key")" ]] || echo "WARN: $key is empty, S3/recognition will not work yet"
  done
  [[ -z "$(env_value SHOPIFY_SHOP_DOMAIN)" ]] \
    || echo "WARN: SHOPIFY_SHOP_DOMAIN is set, make sure it is a development store"
}

cmd_deploy() {
  check_env_file
  echo "Context: $(kubectl config current-context)"
  local existed=0
  kubectl -n "$NS" get deployment/comic-helper >/dev/null 2>&1 && existed=1

  kubectl apply -k "$ROOT/infra/k3s-poc"
  # Server-side apply: no last-applied annotation that would duplicate the secret data.
  kubectl -n "$NS" create secret generic comics-env --from-env-file="$ENV_FILE" \
    --dry-run=client -o yaml | kubectl apply --server-side --force-conflicts -f - >/dev/null
  echo "secret/comics-env applied"
  # Picks up a freshly imported image and changed secrets.
  (( existed )) && kubectl -n "$NS" rollout restart deployment/comic-helper deployment/n8n >/dev/null

  local res
  for res in statefulset/postgres deployment/n8n; do
    kubectl -n "$NS" rollout status "$res" --timeout=600s
  done
  kubectl -n "$NS" rollout status deployment/comic-helper --timeout=180s \
    || die "comic-helper not ready; image missing? run '$0 build'"
  cmd_status
}

cmd_status() {
  kubectl -n "$NS" get pods,pvc
  echo
  echo "Access only via: $0 forward"
  echo "  n8n:       http://localhost:$N8N_PORT/"
  echo "  Review-UI: http://localhost:$HELPER_PORT/review/   (user: any, password: REVIEW_PASSWORD)"
}

cmd_forward() {
  echo "n8n on http://localhost:$N8N_PORT/, review UI on http://localhost:$HELPER_PORT/review/ (Ctrl-C to stop)"
  kubectl -n "$NS" port-forward --address 127.0.0.1 svc/n8n "$N8N_PORT:5678" &
  kubectl -n "$NS" port-forward --address 127.0.0.1 svc/comic-helper "$HELPER_PORT:8080" &
  trap 'kill $(jobs -p) 2>/dev/null' EXIT INT TERM
  wait
}

cmd_delete() {
  kubectl get namespace "$NS" -l "$POC_LABEL" -o name | grep -q . \
    || die "namespace $NS has no label $POC_LABEL, refusing to delete"
  echo "Context: $(kubectl config current-context)"
  read -r -p "Delete namespace $NS including the n8n database? Type 'loeschen': " answer
  [[ "$answer" == loeschen ]] || die "aborted"
  kubectl delete namespace "$NS" --wait=true
  echo "Namespace $NS removed. $ENV_FILE was kept."
}

case "${1:-}" in
  env|build|deploy|status|forward|delete) "cmd_$1" ;;
  *) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
