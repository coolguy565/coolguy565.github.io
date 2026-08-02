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
  if repo_installed; then
    echo "==> [$REPO] already in $PACMAN_CONF, keeping existing entry"
  else
    echo "==> Adding [$REPO] to $PACMAN_CONF"
    printf '\n[%s]\nSigLevel = Required DatabaseOptional\nServer = %s\n' "$REPO" "$SERVER" >> "$PACMAN_CONF"
  fi
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

read_key() {
  # arrow keys / enter from the real terminal, not stdin (script may be piped)
  local key seq
  IFS= read -rsn1 key </dev/tty
  if [[ $key == $'\e' ]]; then
    IFS= read -rsn2 seq </dev/tty 2>/dev/null || seq=''
    case "$seq" in
      '[A') echo up ;;
      '[B') echo down ;;
      '[C') echo right ;;
      '[D') echo left ;;
    esac
  elif [[ $key == $'\r' || $key == $'\n' ]]; then
    echo enter
  else
    echo "$key"
  fi
}

build_options() {
  options=()
  if repo_installed; then
    options+=("Uninstall repo")
    repo_outdated && options+=("Update repo")
  else
    options+=("Install repo")
  fi
  options+=("Quit")
}

render() {
  printf '\033[2J\033[H'
  banner
  echo
  echo "Repository: $REPO"
  echo "Server: $SERVER"
  echo "Key: $KEYID"
  echo
  echo "Repo status: $status"
  echo
  echo "Use arrow keys to move, Enter to select:"
  for i in "${!options[@]}"; do
    if [[ $i -eq $current ]]; then
      printf '\033[1;32;7m  > %s  \033[0m\n' "${options[$i]}"
    else
      printf '    %s\n' "${options[$i]}"
    fi
  done
}

status=""
current=0

# enter raw mode, restore on exit
saved_terminal=$(stty -g)
stty raw -echo
trap 'stty "$saved_terminal"' EXIT INT TERM

while true; do
  installed=0; repo_installed && installed=1
  outdated=0; [[ $installed -eq 1 ]] && repo_outdated && outdated=1
  status="NOT INSTALLED"
  [[ $installed -eq 1 ]] && status="INSTALLED"
  [[ $outdated -eq 1 ]] && status+=" (update available)"

  build_options
  [[ $current -ge ${#options[@]} ]] && current=$(( ${#options[@]} - 1 ))

  render
  case "$(read_key)" in
    up)    ((current = (current - 1 + ${#options[@]}) % ${#options[@]})) ;;
    down)  ((current = (current + 1) % ${#options[@]})) ;;
    enter) break ;;
    q)     stty "$saved_terminal"; exit 0 ;;
  esac
done

stty "$saved_terminal"

case "${options[$current]}" in
  "Install repo")   install_repo ;;
  "Uninstall repo") uninstall_repo ;;
  "Update repo")    update_repo ;;
  "Quit")           echo "Bye!" ;;
esac
