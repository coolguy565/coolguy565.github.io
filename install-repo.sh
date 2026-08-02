#!/usr/bin/env bash
# Interactive installer for the coolguy565 pacman repository.
# Usage:
#   sudo bash install-repo.sh              -> interactive menu
#   sudo bash install-repo.sh package...   -> non-interactive: setup + install packages

set -euo pipefail

REPO="coolguy565"
SERVER="https://github.com/coolguy565/coolguy565.github.io/releases/download/coolguy565"
KEYID="E36138CC5F015492A1D620581C4F28ACC1A18345"
PACMAN_CONF="/etc/pacman.conf"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo)." >&2
  exit 1
fi

setup_repo() {
  echo "==> Adding [$REPO] to $PACMAN_CONF"
  if grep -q "^\[$REPO\]" "$PACMAN_CONF"; then
    echo "    already present, skipping"
  else
    printf '\n[%s]\nSigLevel = Required DatabaseOptional\nServer = %s\n' "$REPO" "$SERVER" >> "$PACMAN_CONF"
    echo "    added"
  fi

  echo "==> Trusting the signing key"
  if [[ ! -f /etc/pacman.d/gnupg/pubring.gpg ]] && [[ ! -d /etc/pacman.d/gnupg/private-keys-v1.d ]]; then
    echo "    initializing pacman keyring..."
    pacman-key --init
    pacman-key --populate archlinux
  fi
  curl -fsSL -o "/tmp/$REPO.asc" "$SERVER/$REPO.asc"
  pacman-key --add "/tmp/$REPO.asc"
  pacman-key --lsign-key "$KEYID"
  rm -f "/tmp/$REPO.asc"

  echo "==> Syncing repositories"
  pacman -Sy
  echo "==> [$REPO] repo is ready."
}

install() {
  pacman -S --needed "$@"
}

# non-interactive: setup + install given packages
if [[ $# -gt 0 ]]; then
  setup_repo
  install "$@"
  exit 0
fi

# interactive menu
setup_repo

while true; do
  echo
  echo "What would you like to install?"
  echo "  1) google-chrome"
  echo "  2) yay"
  echo "  3) linux-cool (kernel + headers + docs)"
  echo "  4) everything"
  echo "  0) quit"
  printf "Choice: "
  read -r choice
  case "$choice" in
    1) install google-chrome ;;
    2) install yay ;;
    3) install linux-cool linux-cool-headers linux-cool-docs ;;
    4) install google-chrome yay linux-cool linux-cool-headers linux-cool-docs ;;
    0) echo "Bye!"; exit 0 ;;
    *) echo "Invalid choice: $choice" ;;
  esac
done
