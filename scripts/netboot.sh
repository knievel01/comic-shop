#!/usr/bin/env bash
# Serves the comics installer ISO for UEFI network boot (ADR-0031): proxyDHCP + TFTP + HTTP on this machine.
# The router's DHCP stays untouched; dnsmasq only adds the boot file for PXE clients.
#
#   sudo not needed up front (uses sudo for dnsmasq/ufw). Stop with Ctrl+C, everything is cleaned up.
#   ISO=os/build/comics-comics-01.iso IFACE=eno1 scripts/netboot.sh
#
# The ISO is the same one as for the USB stick (nocloud seed inside), so the install is identical.
# The client loads the whole ISO into RAM (about 4 GB): use a laptop with >= 8 GB RAM, wired LAN.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BUILD="$HERE/../os/build"
ISO="${ISO:-$BUILD/comics-comics-01.iso}"
IFACE="${IFACE:-$(ip route show default | awk '{print $5; exit}')}"
HTTP_PORT="${HTTP_PORT:-8000}"
ROOT="$BUILD/netboot"
# dnsmasq drops its capabilities, so it cannot read below a 750 home directory: TFTP root lives outside.
TFTP_ROOT=/var/lib/comics-netboot/tftp
SHIM=/usr/lib/shim/shimx64.efi.signed
GRUBNET=/usr/lib/grub/x86_64-efi-signed/grubnetx64.efi.signed

die() { echo "ERROR: $*" >&2; exit 1; }
[[ -s "$ISO" ]] || die "ISO not found: $ISO (build it with os/build-iso.sh)"
for bin in dnsmasq xorriso python3 ufw; do command -v "$bin" >/dev/null || die "missing $bin"; done
for f in "$SHIM" "$GRUBNET"; do [[ -s "$f" ]] || die "missing $f (apt install shim-signed grub-efi-amd64-signed)"; done

IP="$(ip -4 -o addr show dev "$IFACE" | awk '{split($4,a,"/"); print a[1]; exit}')"
NET="$(ip -4 route show dev "$IFACE" scope link | awk '{print $1; exit}')"
[[ -n "$IP" && -n "$NET" ]] || die "no IPv4 network on $IFACE"
echo "Interface $IFACE, server $IP, network $NET"

# 1. Boot files (kernel and initrd come from the ISO itself, so they always match).
rm -rf "$ROOT"; mkdir -p "$ROOT/tftp/grub" "$ROOT/http"
cp "$SHIM" "$ROOT/tftp/bootx64.efi"
cp "$GRUBNET" "$ROOT/tftp/grubx64.efi"
xorriso -osirrox on -indev "$ISO" -extract /casper/vmlinuz "$ROOT/http/vmlinuz" \
  -extract /casper/initrd "$ROOT/http/initrd" >/dev/null 2>&1
ln -s "$(readlink -f "$ISO")" "$ROOT/http/comics.iso"
chmod u+r "$ROOT/http/vmlinuz" "$ROOT/http/initrd"
cat > "$ROOT/tftp/grub/grub.cfg" <<GRUB
# No timeout: someone has to confirm, the install wipes the whole disk of the booting machine.
set timeout=-1
set default=0
menuentry "Comic-Rechner per Netzwerk installieren (LOESCHT DIE GANZE SSD)" {
    linux  (http,$IP:$HTTP_PORT)/vmlinuz ip=dhcp rootfstype=ramfs url=http://$IP:$HTTP_PORT/comics.iso autoinstall ds=nocloud\;s=/cdrom/nocloud/ ---
    initrd (http,$IP:$HTTP_PORT)/initrd
}
GRUB
cat > "$ROOT/dnsmasq.conf" <<CONF
port=0
user=root
group=root
interface=$IFACE
bind-interfaces
dhcp-range=${NET%/*},proxy
pxe-service=X86-64_EFI,"Comic-Rechner installieren",bootx64.efi
pxe-service=BC_EFI,"Comic-Rechner installieren",bootx64.efi
enable-tftp
tftp-root=$TFTP_ROOT
log-dhcp
CONF

# Publish the TFTP files where dnsmasq can read them.
sudo rm -rf "$TFTP_ROOT"; sudo mkdir -p "$TFTP_ROOT"; sudo cp -r "$ROOT/tftp/." "$TFTP_ROOT/"; sudo chmod -R a+rX "$TFTP_ROOT"

# 2. Firewall (opened only for this network, removed on exit).
# DHCP discovers come from 0.0.0.0, so port 67 must be open on the interface, not just for $NET.
RULES=("in on $IFACE to any port 67 proto udp" "from $NET to any port 69,4011 proto udp" "from $NET to any port $HTTP_PORT proto tcp")
cleanup() {
  trap - EXIT INT TERM
  [[ -n "${HTTP_PID:-}" ]] && kill "$HTTP_PID" 2>/dev/null || true
  for r in "${RULES[@]}"; do sudo ufw --force delete allow $r >/dev/null 2>&1 || true; done
  sudo rm -rf /var/lib/comics-netboot
  echo "Netboot stopped, firewall rules removed."
}
trap cleanup EXIT INT TERM
for r in "${RULES[@]}"; do sudo ufw allow $r >/dev/null; done

# 3. Serve.
python3 -m http.server "$HTTP_PORT" --bind "$IP" --directory "$ROOT/http" >"$ROOT/http.log" 2>&1 &
HTTP_PID=$!
echo "Ready. Boot the laptop via UEFI network boot (F12 -> 'UEFI PXE' / network), confirm the menu entry."
echo "Log: $ROOT/http.log. Ctrl+C stops the server."
sudo dnsmasq --keep-in-foreground --conf-file="$ROOT/dnsmasq.conf" --log-facility=-
