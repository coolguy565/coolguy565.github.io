# Custom pacman repository (hosted on GitHub Pages)

Every push to `packages/` triggers GitHub Actions, which builds the package
with `makepkg`, signs it and the repository database with a dedicated GPG key,
then deploys everything to the `gh-pages` branch of this repo. GitHub Pages
serves it, so any Arch machine can add it to pacman.

## Repository layout

```
packages/<pkgname>/PKGBUILD   # one directory per package (all are built)
build.sh                      # builds packages, signs them, runs repo-add
.github/workflows/build.yml   # CI: build + deploy to GitHub Pages
```

## One-time setup

1. The repo is `coolguy565/coolguy565.github.io` (public). Pages is set to
   serve the `gh-pages` branch, which holds only the built repo files.

2. A dedicated GPG signing key is used (`E36138CC5F015492A1D620581C4F28ACC1A18345`).
   Set these repo secrets
   (Settings > Secrets and variables > Actions):
   | Secret            | Value                                                      |
   |-------------------|------------------------------------------------------------|
   | `GPG_KEY_B64`     | `gpg --export-secret-keys --armor KEYID \| base64 -w0`     |
   | `GPG_PASSPHRASE`  | your key's passphrase (set this one yourself)              |
   | `GPGKEY`          | new key fingerprint                                        |
   | `PACKAGER_NAME`   | your key's UID name                                        |
   | `PACKAGER_EMAIL`  | your key's UID email                                       |

3. Trigger a build: push a commit or use the **Run workflow** button
   (Actions > build). It deploys to the `gh-pages` branch.

## Adding a package

Copy a directory into `packages/`:

```
packages/hello-pacman/PKGBUILD
packages/hello-pacman/hello.sh
```

Push, wait for the build, done.

## Using the repo on an Arch machine

1. Add the repo to `/etc/pacman.conf` (name must match `REPO_NAME`):
   ```
   [myrepo]
   SigLevel = Required DatabaseOptional
   Server = https://github.com/coolguy565/coolguy565.github.io/releases/download/repo
   ```

2. Import and trust the signing key:
   ```sh
   sudo pacman-key --init
   curl -L -o myrepo.asc https://github.com/coolguy565/coolguy565.github.io/releases/download/repo/myrepo.asc
   sudo pacman-key --add myrepo.asc
   sudo pacman-key --lsign-key E36138CC5F015492A1D620581C4F28ACC1A18345
   ```

3. Sync and install:
   ```sh
   sudo pacman -Sy
   sudo pacman -S hello-pacman
   ```

## Notes / troubleshooting

- **Packages must stay small**: GitHub Pages has a 100 MB per-file limit.
  This is fine for typical packages, not for huge ones.
- `SigLevel = Required DatabaseOptional` verifies every package against your
  key; the database signature is checked when present but not required.
- Each successful build overwrites the `gh-pages` branch (`force_orphan`),
  so the latest packages are always served at the root.
- If a build fails, open the Actions run log — the `::error::` lines from
  `build.sh` point at the cause (usually a missing secret or a bad PKGBUILD).
