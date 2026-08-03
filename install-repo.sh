#!/usr/bin/env bash
# Cool Arch repo manager (Python/TUI backend).
# Usage: curl -fsSL https://zulo.alwaysdata.net/installrepo | sudo bash
set -euo pipefail

URL="https://coolguy565.github.io/install-repo.py"
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
curl -fsSL "$URL" -o "$tmp"
exec python3 "$tmp"
