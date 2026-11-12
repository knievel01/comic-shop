#!/usr/bin/env bash
# Builds the unattended "comics" installer ISO from the official Ubuntu Server ISO.
#
# Usage:
#   SSH_KEYS_FILE=~/.ssh/id_ed25519.pub REPO_URL=https://github.com/<user>/comic-shop.git \
#     os/build-iso.sh
#
# Env:
#   UBUNTU_VERSION  release directory on releases.ubuntu.com (default 24.04)
#   UBUNTU_ISO      exact ISO file name (default: newest *live-server-amd64.iso in SHA256SUMS)
#   SSH_KEYS_FILE   file with one or more public keys for user "comicadmin" (required)
#   REPO_URL        git URL used by ansible-pull on first boot (required)
#   REPO_BRANCH     default: main
#   HOSTNAME_NEW    default: comics-01
#   OUT             output path (default: os/build/comics-<hostname>.iso)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BUILD="$HERE/build"
UBUNTU_VERSION="${UBUNTU_VERSION:-24.04}"
REPO_BRANCH="${REPO_BRANCH:-main}"
HOSTNAME_NEW="${HOSTNAME_NEW:-comics-01}"
OUT="${OUT:-$BUILD/comics-${HOSTNAME_NEW}.iso}"
MIRROR="https://releases.ubuntu.com/${UBUNTU_VERSION}"
# Ubuntu CD image signing key
UBUNTU_KEY_FPR="843938DF228D22F7B3742BC0D94AA3F0EFE21092"

die() { echo "ERROR: $*" >&2; exit 1; }
: "${SSH_KEYS_FILE:?SSH_KEYS_FILE must point to a public key file}"
: "${REPO_URL:?REPO_URL must be set}"
[[ -s "$SSH_KEYS_FILE" ]] || die "$SSH_KEYS_FILE is empty"
grep -q "PRIVATE KEY" "$SSH_KEYS_FILE" && die "$SSH_KEYS_FILE contains a private key"
for bin in xorriso curl sha256sum gpg; do command -v "$bin" >/dev/null || die "missing $bin"; done

mkdir -p "$BUILD"
cd "$BUILD"

# 1. Download checksums + signature and verify them.
curl -fsSLO "$MIRROR/SHA256SUMS"
curl -fsSLO "$MIRROR/SHA256SUMS.gpg"
GNUPGHOME="$(mktemp -d)"; export GNUPGHOME
gpg --batch --keyserver hkps://keyserver.ubuntu.com --recv-keys "$UBUNTU_KEY_FPR" >/dev/null 2>&1 \
  || die "could not fetch Ubuntu signing key"
LC_ALL=C gpg --batch --verify SHA256SUMS.gpg SHA256SUMS 2>&1 | grep -q "Good signature" \
  || die "SHA256SUMS signature invalid"
rm -rf "$GNUPGHOME"

UBUNTU_ISO="${UBUNTU_ISO:-$(grep -o 'ubuntu-[0-9.]*-live-server-amd64.iso' SHA256SUMS | sort -V | tail -1)}"
[[ -n "$UBUNTU_ISO" ]] || die "no live-server ISO in SHA256SUMS"
echo "Base image: $UBUNTU_ISO"

# 2. Download ISO (cached) and verify checksum.
[[ -f "$UBUNTU_ISO" ]] || curl -fL --progress-bar -o "$UBUNTU_ISO" "$MIRROR/$UBUNTU_ISO"
grep " \*\?$UBUNTU_ISO\$" SHA256SUMS | sed 's/ \*/  /' | sha256sum -c - || die "checksum mismatch"

# 3. Assemble the nocloud seed.
rm -rf nocloud && mkdir nocloud
keys_yaml="$(grep -v '^\s*$' "$SSH_KEYS_FILE" | sed 's/^/          - /')"
KEYS_YAML="$keys_yaml" HOSTNAME_NEW="$HOSTNAME_NEW" REPO_URL="$REPO_URL" REPO_BRANCH="$REPO_BRANCH" \
python3 - "$HERE/autoinstall/user-data" nocloud/user-data <<'PY'
import os, sys
src, dst = sys.argv[1], sys.argv[2]
text = open(src).read()
for placeholder, var in [("@@SSH_KEYS@@", "KEYS_YAML"), ("@@HOSTNAME@@", "HOSTNAME_NEW"),
                         ("@@REPO_URL@@", "REPO_URL"), ("@@REPO_BRANCH@@", "REPO_BRANCH")]:
    text = text.replace(placeholder, os.environ[var])
assert "@@" not in text, "unreplaced placeholder"
open(dst, "w").write(text)
PY
cp "$HERE/autoinstall/meta-data" nocloud/meta-data
cp "$HERE/firstboot/comics-firstboot.service" "$HERE/firstboot/comics-firstboot.sh" nocloud/

# 4. Boot menu: default entry runs autoinstall after 10 s.
xorriso -osirrox on -indev "$UBUNTU_ISO" -extract /boot/grub/grub.cfg grub.orig.cfg >/dev/null 2>&1
chmod u+w grub.orig.cfg
{
  cat <<'GRUB'
set timeout=10
set default=0
loadfont unicode
menuentry "Comic-Rechner automatisch installieren (LOESCHT DIE GANZE SSD)" {
    set gfxpayload=keep
    linux   /casper/vmlinuz quiet autoinstall ds=nocloud\;s=/cdrom/nocloud/ ---
    initrd  /casper/initrd
}
GRUB
  # Keep the original entries (manual install, memtest, ...) below ours.
  sed -e '/^set timeout/d' -e '/^set default/d' -e '/^loadfont/d' grub.orig.cfg
} > grub.cfg

# 5. Repack, re-using the original boot setup (BIOS + UEFI).
rm -f "$OUT"
xorriso -indev "$UBUNTU_ISO" -outdev "$OUT" \
  -map nocloud /nocloud \
  -map grub.cfg /boot/grub/grub.cfg \
  -boot_image any replay \
  -volid "COMICS_$(echo "$HOSTNAME_NEW" | tr 'a-z-' 'A-Z_' | cut -c1-20)"

( cd "$(dirname "$OUT")" && sha256sum "$(basename "$OUT")" > "$(basename "$OUT").sha256" )
echo "Fertig: $OUT"
cat "$OUT.sha256"
