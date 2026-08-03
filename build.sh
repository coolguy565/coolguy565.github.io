#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

REPO_NAME="${REPO_NAME:-coolguy565}"
OUT_DIR="${OUT_DIR:-repo}"
GPG_KEY_B64="${GPG_KEY_B64:-}"
GPG_PASSPHRASE="${GPG_PASSPHRASE:-}"
GPGKEY="${GPGKEY:-}"
PACKAGER_NAME="${PACKAGER_NAME:-}"
PACKAGER_EMAIL="${PACKAGER_EMAIL:-}"

if [[ -z "$GPG_KEY_B64" ]]; then
  echo "::error::GPG_KEY_B64 secret is not set" >&2
  exit 1
fi

export GNUPGHOME="${GNUPGHOME:-$HOME/.gnupg}"
mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"
printf 'allow-preset-passphrase\n' > "$GNUPGHOME/gpg-agent.conf"

echo "$GPG_KEY_B64" | base64 -d | gpg --batch --import

gpgconf --kill gpg-agent || true
gpgconf --launch gpg-agent

KEYGRIP="$(gpg --with-keygrip --list-secret-keys "$GPGKEY" 2>/dev/null | awk '/Keygrip/ {print $3; exit}')"
if [[ -z "$KEYGRIP" ]]; then
  echo "::error::no keygrip found for GPGKEY=$GPGKEY" >&2
  exit 1
fi

GPG_PRESET="$(command -v gpg-preset-passphrase || { ls /usr/bin/gnupg/gpg-preset-passphrase 2>/dev/null || ls /usr/lib/gnupg/gpg-preset-passphrase 2>/dev/null || true; })"
if [[ -n "$GPG_PRESET" ]]; then
  printf '%s' "$GPG_PASSPHRASE" | "$GPG_PRESET" --preset "$KEYGRIP"
fi

printf 'GPGKEY="%s"\nPACKAGER="%s <%s>"\n' "$GPGKEY" "$PACKAGER_NAME" "$PACKAGER_EMAIL" > "$HOME/.makepkg.conf"

mkdir -p "$OUT_DIR"
shopt -s nullglob

# ---- incremental build: skip packages whose source is unchanged since the
# last successful build (fingerprint stored in OUT_DIR/build-manifest.json) ----
MANIFEST_FILE="$OUT_DIR/build-manifest.json"
OLD_FP_FILE="/tmp/old_fp.tsv"
FP_FILE="/tmp/fp.tsv"

fingerprint() {
  find "$1" -type f \
    -not -path '*/src/*' \
    -not -path '*/pkg/*' \
    -not -path '*/__pycache__/*' \
    -not -name '*.pkg.tar.zst' \
    -not -name '*.pkg.tar.zst.sig' \
    -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}'
}

python3 - "$MANIFEST_FILE" > "$OLD_FP_FILE" <<'PY' || true
import json, sys, os
if os.path.exists(sys.argv[1]):
    for k, v in json.load(open(sys.argv[1])).items():
        print(f"{k}\t{v}")
PY
: > "$FP_FILE"

for pkgdir in packages/*/; do
  [[ -f "$pkgdir/PKGBUILD" ]] || continue
  name="${pkgdir%/}"; name="${name##*/}"
  if [[ -f "$pkgdir/.heavy" ]]; then
    echo "::group::Skipping ${name} (heavy - built locally in firejail)"
    echo "::endgroup::"
    continue
  fi
  fp=$(fingerprint "$pkgdir")
  oldfp=$(awk -F'\t' -v n="$name" '$1==n{print $2}' "$OLD_FP_FILE")
  if [[ -n "$oldfp" && "$oldfp" == "$fp" ]] \
     && compgen -G "$OUT_DIR/${name}-*.pkg.tar.zst" >/dev/null; then
    echo "::group::Skipping ${name} (unchanged since last successful build)"
    echo "::endgroup::"
    echo -e "$name\t$fp" >> "$FP_FILE"
    continue
  fi
  echo "::group::Building ${name}"
  mkg_args=(-s --noconfirm)
  [[ -f "$pkgdir/.skippgpcheck" ]] && mkg_args+=(--skippgpcheck)
  ( cd "$pkgdir" && makepkg "${mkg_args[@]}" --sign ) \
    || echo "::warning::build failed: ${name}"
  echo "::endgroup::"
  echo -e "$name\t$fp" >> "$FP_FILE"
done

python3 - "$MANIFEST_FILE" "$FP_FILE" <<'PY' || true
import json, sys
rows = {}
for line in open(sys.argv[2]):
    line = line.rstrip("\n")
    if not line:
        continue
    n, f = line.split("\t")
    rows[n] = f
json.dump(rows, open(sys.argv[1], "w"), indent=2)
PY

echo "::group::Creating repository database"
cd "$OUT_DIR"
find ../packages -maxdepth 2 -name '*.pkg.tar.zst' -exec cp {} . \;
find ../packages -maxdepth 2 -name '*.pkg.tar.zst.sig' -exec cp {} . \;

# drop stale older versions of rebuilt packages (CI release accumulates old builds)
for pkgdir in ../packages/*/; do
  [[ -f "$pkgdir/PKGBUILD" ]] || continue
  pnames=$(cd "$pkgdir" && set +eu && source PKGBUILD 2>/dev/null && echo "${pkgname[@]}" || true)
  for pn in $pnames; do
    for old in $(ls ${pn}-*.pkg.tar.zst 2>/dev/null | sort -V | head -n -1); do
      echo "removing stale $old"
      rm -f "$old" "${old}.sig"
    done
  done
done
repo-add --sign -v -R "$REPO_NAME.db.tar.gz" ./*.pkg.tar.zst
gpg --export --armor "$GPGKEY" > "$REPO_NAME.asc"
echo "::endgroup::"

echo "Packages built and database created in ./$OUT_DIR"
