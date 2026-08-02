#!/usr/bin/env bash
# Interactive manager for the coolguy565 pacman repository.
# Usage: sudo bash install-repo.sh

set -euo pipefail

REPO="coolguy565"
SERVER="https://github.com/coolguy565/coolguy565.github.io/releases/download/coolguy565"
KEYID="E36138CC5F015492A1D620581C4F28ACC1A18345"
PACMAN_CONF="/etc/pacman.conf"
SYNC_DB="/var/lib/pacman/sync/$REPO.db"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo)." >&2
  exit 1
fi

banner() {
  if command -v figlet >/dev/null 2>&1; then
    if command -v lolcat >/dev/null 2>&1; then
      figlet -f slant "$REPO repo" | lolcat
    else
      figlet -f slant "$REPO repo"
    fi
  else
    echo "================="
    echo "  $REPO pacman repo"
    echo "================="
  fi
}

repo_installed() {
  grep -q "^\[$REPO\]" "$PACMAN_CONF"
}

repo_outdated() {
  # server db differs from the last synced copy -> an update is available
  curl -fsSL -o "/tmp/$REPO.db" "$SERVER/$REPO.db" 2>/dev/null || return 0
  [[ ! -f "$SYNC_DB" ]] && return 0
  cmp -s "/tmp/$REPO.db" "$SYNC_DB" && return 1 || return 0
}

trust_key() {
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
}

install_repo() {
  echo "==> Adding [$REPO] to $PACMAN_CONF"
  printf '\n[%s]\nSigLevel = Required DatabaseOptional\nServer = %s\n' "$REPO" "$SERVER" >> "$PACMAN_CONF"
  trust_key
  echo "==> Syncing repositories"
  pacman -Sy
  echo "==> [$REPO] repo installed."
}

update_repo() {
  trust_key
  echo "==> Syncing repositories"
  pacman -Sy
  echo "==> [$REPO] repo updated."
}

uninstall_repo() {
  echo "==> Removing [$REPO] from $PACMAN_CONF"
  sed -i "/^\[$REPO\]$/,/^$/d" "$PACMAN_CONF"
  rm -f "$SYNC_DB" "/var/lib/pacman/sync/$REPO.files" \
        "/var/lib/pacman/sync/$REPO.db.sig" "/var/lib/pacman/sync/$REPO.files.sig"
  echo "==> Removing signing key from pacman keyring"
  pacman-key --delete "$KEYID" 2>/dev/null || true
  echo "==> [$REPO] repo removed. Installed packages are kept."
}

banner
echo

if repo_installed; then
  status="INSTALLED"
  repo_outdated && status+=" (update available)"
else
  status="NOT INSTALLED"
fi
echo "Repo status: $status"

while true; do
  echo
  installed=0
  repo_installed && installed=1
  outdated=0
  if [[ $installed -eq 1 ]]; then
    repo_outdated && outdated=1
  fi

  echo "What would you like to do?"
  echo "  1) $([[ $installed -eq 1 ]] && echo Uninstall || echo Install) repo"
  if [[ $installed -eq 1 && $outdated -eq 1 ]]; then
    echo "  2) Update repo"
    echo "  3) Quit"
  else
    echo "  2) Quit"
  fi
  printf "Choice: "
  read -r choice
  case "$choice" in
    1)
      if [[ $installed -eq 1 ]]; then uninstall_repo; else install_repo; fi
      ;;
    2)
      if [[ $installed -eq 1 && $outdated -eq 1 ]]; then update_repo; else exit 0; fi
      ;;
    3)
      if [[ $installed -eq 1 && $outdated -eq 1 ]]; then exit 0; fi
      echo "Invalid choice: $choice"
      ;;
    *)
      echo "Invalid choice: $choice"
      ;;
  esac
done
