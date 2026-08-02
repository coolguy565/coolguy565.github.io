#!/usr/bin/env bash
set -euo pipefail

nvchecker -c .nvchecker.toml

python3 - <<'PY'
import json
import re
from pathlib import Path

with open('.nvchecker.new.json') as f:
    j = json.load(f)

if isinstance(j.get('data'), dict):
    versions = {k: v.get('version') for k, v in j['data'].items()}
else:
    versions = j

changed = []
for pkg, ver in versions.items():
    if not isinstance(ver, str):
        continue
    ver = ver.lstrip('v')
    pk = Path('packages') / pkg / 'PKGBUILD'
    if not pk.exists():
        continue
    text = pk.read_text()
    m = re.search(r'^pkgver=([^\n]+)', text, re.M)
    if not m:
        continue
    old = m.group(1).strip().strip('"\'')
    if old == ver:
        continue
    text = re.sub(r'^pkgver=.*$', 'pkgver=' + ver, text, flags=re.M)
    text = re.sub(r'^pkgrel=.*$', 'pkgrel=1', text, flags=re.M)
    pk.write_text(text)
    changed.append(pkg)
    print(f'updated {pkg}: {old} -> {ver}')

if not changed:
    print('no updates')
PY
