#!/usr/bin/env bash
# Sandbox on the MacBook: postgres, n8n and comic-helper as Docker Compose in OrbStack.
# See docs/SANDBOX-MAC.md and ADR-0039. Not for the comic machine (that is K3s, docs/INSTALL.md).
#
# Usage: scripts/sandbox-orbstack.sh env|up|build|import|status|logs|down|reset
#   env     create the secrets file (internal secrets generated, AWS/Anthropic left empty)
#   up      build the comic-helper image and start everything (restarts it after a code change)
#   build   only build the comic-helper image
#   import  import workflows/ into the running n8n (credentials are created in the UI)
#   status  show containers and URLs
#   logs    follow logs, optionally of one service: logs comic-helper
#   down    stop and remove the containers, volumes (n8n database) are kept
#   reset   like down, additionally removes the volumes (n8n database gone, env file is kept)
#
# Env:
#   COMICS_ENV_FILE  default: ~/.config/comics/comics.env (mode 600, never commit)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${COMICS_ENV_FILE:-$HOME/.config/comics/comics.env}"
COMPOSE_FILE="$ROOT/infra/sandbox-orbstack/compose.yaml"
N8N_URL=http://localhost:5678
REVIEW_URL=http://localhost:8080
export COMICS_ENV_FILE="$ENV_FILE"

die() { echo "ERROR: $*" >&2; exit 1; }
env_value() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2-; }
# stat and sed -i differ between macOS (BSD) and Linux (GNU)
file_mode() { if [[ "$(uname)" == Darwin ]]; then stat -f %Lp "$1"; else stat -c %a "$1"; fi; }
# write through a temp file created with umask 077, so the secrets are never world-readable
sed_inplace() { local file=$1; shift; (umask 077 && sed "$@" "$file" > "$file.tmp") && mv -f "$file.tmp" "$file"; }
compose() { docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"; }

cmd_env() {
  [[ -e "$ENV_FILE" ]] && die "$ENV_FILE exists already (N8N_ENCRYPTION_KEY must stay stable), edit it instead"
  install -d -m 700 "$(dirname "$ENV_FILE")"
  (umask 077 && cp "$ROOT/.env.example" "$ENV_FILE")
  chmod 600 "$ENV_FILE"
  local key
  for key in N8N_ENCRYPTION_KEY POSTGRES_PASSWORD HELPER_TOKEN; do
    sed_inplace "$ENV_FILE" "s|^$key=.*|$key=$(openssl rand -hex 32)|"
  done
  sed_inplace "$ENV_FILE" -e "s|^WEBHOOK_URL=.*|WEBHOOK_URL=$N8N_URL/|" \
    -e "s|^REVIEW_BASE_URL=.*|REVIEW_BASE_URL=$REVIEW_URL|"
  echo "Created $ENV_FILE (mode 600)."
  echo "Fill in at least S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, ANTHROPIC_API_KEY."
  echo "Shopify: use a development store only. Test bucket only, never production data (ADR-0027)."
}

check_env_file() {
  [[ -s "$ENV_FILE" ]] || die "$ENV_FILE missing, run: $0 env"
  (( (8#$(file_mode "$ENV_FILE") & 077) == 0 )) || die "$ENV_FILE must not be readable by group/others"
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

need_docker() { docker info >/dev/null 2>&1 || die "Docker is not reachable, start OrbStack"; }

cmd_build() { check_env_file; need_docker; compose build comic-helper; }

cmd_up() {
  check_env_file; need_docker
  # --build: a code change is picked up; compose recreates only the containers that changed
  compose up -d --build --wait
  cmd_status
}

cmd_import() {
  check_env_file; need_docker
  tar -C "$ROOT/workflows" -cf - --exclude='README.md' . \
    | compose exec -T n8n sh -c 'rm -rf /tmp/wf-in && mkdir -p /tmp/wf-in && tar -C /tmp/wf-in -xf -'
  compose exec -T n8n n8n import:workflow --separate --input=/tmp/wf-in/
  echo "Import done. Create the credentials in the n8n UI (names in docs/SANDBOX-MAC.md), then activate the workflows."
}

cmd_status() {
  need_docker
  compose ps
  echo
  echo "  n8n:       $N8N_URL/   (create the owner account on first visit)"
  echo "  Review-UI: $REVIEW_URL/review/   (password only if REVIEW_PASSWORD is set)"
}

cmd_logs() { check_env_file; need_docker; compose logs -f --tail=100 "$@"; }

cmd_down() { check_env_file; need_docker; compose down; echo "Stopped. Volumes (n8n database) kept."; }

cmd_reset() {
  check_env_file; need_docker
  read -r -p "Remove containers AND volumes including the n8n database? Type 'loeschen': " answer
  [[ "$answer" == loeschen ]] || die "aborted"
  compose down -v
  echo "Removed. $ENV_FILE was kept."
}

case "${1:-}" in
  env|up|build|import|status|down|reset) "cmd_$1" ;;
  logs) shift; cmd_logs "$@" ;;
  *) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
