#!/usr/bin/env bash
# Richtet Tailscale auf dem Comic-Rechner ein (ADR-0025). Läuft auf dem Mac; der Rechner muss per SSH erreichbar sein
# (Kabel oder WLAN, im selben Netz). Das WLAN und alle anderen Einstellungen bleiben unberührt.
#   scripts/tailscale-einrichten.sh 192.168.3.155
set -euo pipefail

HOST="${1:?Aufruf: $0 <IP oder Name des Comic-Rechners>}"
SSH=(ssh -i "${COMICS_SSH_KEY:-$HOME/.ssh/id_ed25519_comics}" "comicadmin@$HOST")
ENV=/etc/comics/comics.env

"${SSH[@]}" true || { echo "Der Rechner antwortet nicht unter $HOST." >&2; exit 1; }

echo "Tailscale-Auth-Key (einmalig, login.tailscale.com/admin/settings/keys)."
echo "Enter ohne Eingabe: Der Rechner zeigt stattdessen einen Anmeldelink."
read -rsp "Key: " KEY; echo
if [[ -n "$KEY" ]]; then
  [[ "$KEY" =~ ^tskey-[A-Za-z0-9_-]+$ ]] || { echo "Das sieht nicht wie ein Tailscale-Key aus (tskey-…)." >&2; exit 1; }
  # via stdin, so the key never shows up in a process list or shell history
  printf '%s\n' "$KEY" | "${SSH[@]}" "read -r k; sudo sed -i '/^TAILSCALE_AUTHKEY=/d' $ENV; \
    printf 'TAILSCALE_AUTHKEY=%s\n' \"\$k\" | sudo tee -a $ENV >/dev/null"
fi
unset KEY

"${SSH[@]}" -t 'sudo comics-update --tags tailscale'
if [[ -z "$("${SSH[@]}" 'tailscale ip -4 2>/dev/null' || true)" ]]; then
  "${SSH[@]}" -t 'sudo tailscale up --hostname comic-server'          # prints the login link
fi
"${SSH[@]}" "sudo sed -i '/^TAILSCALE_AUTHKEY=/d' $ENV"                # the key is single use, do not keep it
echo; echo "Tailscale-Adresse des Rechners:"
"${SSH[@]}" 'tailscale ip -4; tailscale status | head -3'
