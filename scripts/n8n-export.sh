#!/usr/bin/env bash
# Exports all n8n workflows (WITHOUT credentials) into workflows/ of this repo.
# Run after every workflow change, then review and commit:
#   sudo scripts/n8n-export.sh && git diff --stat workflows/ && git commit -am "n8n: ..."
#
# Import direction (fresh install / restore): scripts/n8n-import.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
KC=(k3s kubectl -n comics)
command -v k3s >/dev/null || KC=(kubectl -n comics)

"${KC[@]}" exec deploy/n8n -- sh -c \
  'rm -rf /tmp/wf && n8n export:workflow --all --separate --pretty --output=/tmp/wf/ >/dev/null'
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
"${KC[@]}" exec deploy/n8n -- tar -C /tmp/wf -cf - . | tar -C "$TMP" -xf -

# Stable file names (slug of the workflow name) and no volatile fields -> clean git diffs.
python3 - "$TMP" "$REPO/workflows" <<'PY'
import json, pathlib, re, sys
src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
dst.mkdir(exist_ok=True)
for f in sorted(src.glob("*.json")):
    wf = json.loads(f.read_text())
    for key in ("updatedAt", "createdAt", "versionId", "activeVersionId", "triggerCount", "shared", "versionCounter"):
        wf.pop(key, None)
    for node in wf.get("nodes", []):
        # credential references keep only id+name; never secrets (export is not --decrypted)
        for cred in (node.get("credentials") or {}).values():
            cred.pop("data", None)
    name = wf["name"].lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    (dst / f"{slug}.json").write_text(json.dumps(wf, indent=2, ensure_ascii=False) + "\n")
    print(f"exported {wf['name']} -> workflows/{slug}.json")
PY
