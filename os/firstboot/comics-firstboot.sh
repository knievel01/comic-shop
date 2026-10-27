#!/usr/bin/env bash
# Clones the repo and runs ansible-pull. Used on first boot and later via
# `sudo comics-firstboot` to re-apply the configuration (idempotent).
set -euo pipefail

LOG=/var/log/comics-ansible-pull.log
DONE=/var/lib/comics/firstboot.done
CHECKOUT=/opt/comic-shop

# shellcheck source=/dev/null
source /etc/comics/repo.conf
mkdir -p /var/lib/comics

exec > >(tee -a "$LOG") 2>&1
echo "=== $(date -Is) ansible-pull ${REPO_URL} (${REPO_BRANCH}) ==="

# Wait for network (old office NICs can be slow to come up).
for _ in $(seq 1 60); do
  if git ls-remote --heads "$REPO_URL" >/dev/null 2>&1; then break; fi
  sleep 5
done

ansible-pull \
  --url "$REPO_URL" \
  --checkout "$REPO_BRANCH" \
  --directory "$CHECKOUT" \
  --inventory "$CHECKOUT/os/ansible/inventory.ini" \
  --limit localhost \
  os/ansible/site.yml "$@"

touch "$DONE"
echo "=== $(date -Is) done ==="
