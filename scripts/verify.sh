#!/usr/bin/env bash
# Acceptance check for the comic machine (docs/INSTALL.md step 7).
# Run as root:  sudo /opt/comic-shop/scripts/verify.sh [--skip-scan]
set -uo pipefail

SKIP_SCAN=0
[[ "${1:-}" == "--skip-scan" ]] && SKIP_SCAN=1
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
NS=comics
fails=0

ok()   { printf '  \e[32mOK\e[0m    %s\n' "$*"; }
bad()  { printf '  \e[31mFEHLER\e[0m %s\n' "$*"; fails=$((fails + 1)); }
skip() { printf '  \e[33m--\e[0m    %s\n' "$*"; }
check() { local msg="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$msg"; else bad "$msg"; fi; }

[[ $EUID -eq 0 ]] || { echo "bitte mit sudo ausfuehren"; exit 2; }

echo "System"
check "Erstkonfiguration abgeschlossen" test -f /var/lib/comics/firstboot.done
check "Geheimnisse vorhanden (comics.env, Rechte 600)" \
  bash -c '[[ -s /etc/comics/comics.env && "$(stat -c %a /etc/comics/comics.env)" == 600 ]]'
check "Firewall aktiv" bash -c 'LC_ALL=C ufw status | grep -q "Status: active"'
check "Zeit synchron" bash -c 'LC_ALL=C chronyc tracking | grep -q "Leap status *: Normal"'

echo "K3s"
check "k3s-Dienst aktiv und beim Boot aktiviert" bash -c 'systemctl is-active -q k3s && systemctl is-enabled -q k3s'
check "Node Ready" k3s kubectl wait --for=condition=Ready node --all --timeout=60s
for res in statefulset/postgres deployment/n8n deployment/comic-helper; do
  check "$res bereit" k3s kubectl -n "$NS" rollout status "$res" --timeout=120s
done

echo "Dienste"
check "n8n /healthz" k3s kubectl -n "$NS" exec deploy/n8n -- wget -qO- http://127.0.0.1:5678/healthz
check "comic-helper /healthz" k3s kubectl -n "$NS" exec deploy/comic-helper -- \
  python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz')"
check "n8n ueber Ingress erreichbar" curl -fsk -o /dev/null https://127.0.0.1/healthz
check "Review-Oberflaeche ueber Ingress erreichbar" curl -fsk -o /dev/null https://127.0.0.1/review/healthz
check "n8n-Daten auf persistentem Volume" bash -c \
  "k3s kubectl -n $NS get pvc data-postgres-0 -o jsonpath='{.status.phase}' | grep -q Bound"

echo "S3"
if [[ -f /etc/comics/scan-upload.env && -f /etc/comics/backup.env ]]; then
  key="eingang/_verify/$(hostname)-$(date +%s).txt"
  if ( set -a; . /etc/comics/scan-upload.env; set +a
       echo verify | aws s3 cp --only-show-errors - "s3://$S3_BUCKET/$key" ); then
    ok "Upload mit Scan-Schluessel"
    ( set -a; . /etc/comics/backup.env; set +a; aws s3 rm --only-show-errors "s3://$S3_BUCKET/$key" ) \
      && ok "Aufraeumen mit App-Schluessel" || bad "Testobjekt $key loeschen"
  else
    bad "Upload nach s3://…/eingang/ mit Scan-Schluessel"
  fi
  ( set -a; . /etc/comics/backup.env; set +a
    code="$(curl -s -o /dev/null -w '%{http_code}' "https://$S3_BUCKET.s3.$AWS_DEFAULT_REGION.amazonaws.com/")"
    [[ "$code" == 403 ]] ) && ok "Anonymer Zugriff wird abgelehnt (403)" || bad "Bucket anonym erreichbar?"
else
  bad "scan-upload.env / backup.env fehlen (comics-update nach dem Eintragen der Geheimnisse ausfuehren)"
fi

echo "Timer"
check "Scan-Sync-Timer aktiv" systemctl is-active -q comics-scan-sync.timer
check "Backup-Timer aktiv" systemctl is-active -q comics-backup.timer

echo "Scanner"
if [[ $SKIP_SCAN -eq 1 ]]; then
  skip "Probe-Scan uebersprungen"
elif command -v comics-probe-scan >/dev/null; then
  check "Probe-Scan erzeugt 2-seitige PDF" comics-probe-scan /tmp/verify-probe.pdf
else
  skip "Scanner-Rolle nicht installiert"
fi

echo
if [[ $fails -eq 0 ]]; then echo "Alles gruen."; else echo "$fails Pruefung(en) fehlgeschlagen."; fi
exit $(( fails > 0 ))
