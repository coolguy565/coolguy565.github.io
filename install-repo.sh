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

# state-machine key reader: reads one byte at a time with short timeouts,
# handling both CSI (\e[A) and SS3 (\eOA) arrow sequences.
read_key() {
  local c
  IFS= read -rsN1 c </dev/tty || { echo eof; return; }
  case "$c" in
    $'\e')
      IFS= read -rsN1 -t 0.1 c </dev/tty || { echo esc; return; }
      if [[ $c == '[' || $c == 'O' ]]; then
        IFS= read -rsN1 -t 0.1 c </dev/tty || { echo esc; return; }
        case "$c" in
          A) echo up ;;
          B) echo down ;;
          C) echo right ;;
          D) echo left ;;
          *) echo esc ;;
        esac
      else
        echo esc
      fi
      ;;
    $'\r' | $'\n') echo enter ;;
    q | Q) echo quit ;;
    *) echo "$c" ;;
  esac
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

compute_status() {
  status="NOT INSTALLED"
  repo_installed && status="INSTALLED"
  repo_outdated && status+=" (update available)"
  true
}

# interaction mode: tty -> arrow-key TUI; stdin -> plain menu; none -> auto-install
MODE=none
{ stty -g </dev/tty >/dev/null; } 2>/dev/null && MODE=tty
[[ $MODE == none && -t 0 ]] && MODE=stdin

if [[ $MODE == none ]]; then
  echo "No interactive terminal detected - installing repo automatically."
  install_repo
  exit 0
fi

current=0
build_options

if [[ $MODE == tty ]]; then
  saved_terminal=$(stty -g </dev/tty)
  stty raw -echo </dev/tty
  trap 'stty "$saved_terminal" </dev/tty 2>/dev/null; printf "\033[?25h"; printf "\033[H\033[J"' EXIT INT TERM

  render() {
    compute_status
    printf '\033[H\033[J'
    banner
    echo
    echo "Repository: $REPO"
    echo "Server: $SERVER"
    echo "Key: $KEYID"
    echo
    echo "Repo status: $status"
    echo
    echo "Use arrow keys (or j/k) to move, Enter to select, q to quit:"
    echo
    for i in "${!options[@]}"; do
      if [[ $i -eq $current ]]; then
        printf '\033[1;32;7m  > %s  \033[0m\n' "${options[$i]}"
      else
        printf '    %s\n' "${options[$i]}"
      fi
    done
  }

  while true; do
    render
    case "$(read_key)" in
      up)    ((current = (current - 1 + ${#options[@]}) % ${#options[@]})) ;;
      down)  ((current = (current + 1) % ${#options[@]})) ;;
      enter) break ;;
      quit)  stty "$saved_terminal" </dev/tty; printf '\033[?25h'; echo "Bye!"; exit 0 ;;
    esac
  done

  stty "$saved_terminal" </dev/tty
  printf '\033[?25h'
  echo

elif [[ $MODE == stdin ]]; then
  while true; do
    compute_status
    build_options
    echo
    echo "Repo status: $status"
    echo
    for i in "${!options[@]}"; do
      echo "  $((i + 1))) ${options[$i]}"
    done
    printf "Choice: "
    read -r n || exit 0
    if [[ $n =~ ^[0-9]+$ ]] && (( n >= 1 && n <= ${#options[@]} )); then
      current=$((n - 1))
      break
    fi
    echo "Invalid choice."
  done
fi

case "${options[$current]}" in
  "Install repo")   install_repo ;;
  "Uninstall repo") uninstall_repo ;;
  "Update repo")    update_repo ;;
  "Quit")           echo "Bye!" ;;
esac
