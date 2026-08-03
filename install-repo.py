#!/usr/bin/env python3
# Cool Arch pacman repo manager - curses TUI.
# Usage: curl -fsSL https://zulo.alwaysdata.net/installrepo | sudo bash
import curses
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request

REPO = "coolguy565"
KEYID = "E36138CC5F015492A1D620581C4F28ACC1A18345"
SERVER = "https://github.com/coolguy565/coolguy565.github.io/releases/download/coolguy565"
PACMAN_CONF = "/etc/pacman.conf"
SYNC_DB = f"/var/lib/pacman/sync/{REPO}.db"

BANNER = """   ______            __   ___              __
  / ____/___  ____  / /  /   |  __________/ /_
 / /   / __ \\/ __ \\/ /  / /| | / ___/ ___/ __ \\
/ /___/ /_/ / /_/ / /  / ___ |/ /  / /__/ / / /
\\____/\\____/\\____/_/  /_/  |_/_/   \\___/_/ /_/"""


def run(cmd, check=False):
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def repo_installed():
    if not os.path.exists(PACMAN_CONF):
        return False
    return any(l.strip() == f"[{REPO}]" for l in open(PACMAN_CONF))


def repo_outdated():
    try:
        with urllib.request.urlopen(f"{SERVER}/{REPO}.db", timeout=15) as r:
            remote = r.read()
    except Exception:
        return True
    if not os.path.exists(SYNC_DB):
        return True
    with open(SYNC_DB, "rb") as f:
        return f.read() != remote


def trust_key():
    if not (os.path.exists("/etc/pacman.d/gnupg/pubring.gpg")
            or os.path.isdir("/etc/pacman.d/gnupg/private-keys-v1.d")):
        run(["pacman-key", "--init"])
        run(["pacman-key", "--populate", "archlinux"])
    asc = tempfile.NamedTemporaryFile(delete=False)
    asc.close()
    try:
        urllib.request.urlretrieve(f"{SERVER}/{REPO}.asc", asc.name)
        run(["pacman-key", "--add", asc.name])
        run(["pacman-key", "--lsign-key", KEYID])
    finally:
        os.unlink(asc.name)


def install_repo():
    if not repo_installed():
        with open(PACMAN_CONF, "a") as f:
            f.write(f"\n[{REPO}]\nSigLevel = Required DatabaseOptional\nServer = {SERVER}\n")
    trust_key()
    run(["pacman", "-Sy"])


def update_repo():
    trust_key()
    run(["pacman", "-Sy"])


def uninstall_repo():
    with open(PACMAN_CONF) as f:
        lines = f.readlines()
    out = []
    skip = False
    for i, l in enumerate(lines):
        if l.strip() == f"[{REPO}]":
            skip = True
        elif skip and l.strip().startswith("["):
            skip = False
        if not skip:
            out.append(l)
    with open(PACMAN_CONF, "w") as f:
        f.writelines(out)
    for f in [SYNC_DB, f"{SYNC_DB}.sig", f"/var/lib/pacman/sync/{REPO}.files", f"/var/lib/pacman/sync/{REPO}.files.sig"]:
        if os.path.exists(f):
            os.unlink(f)
    run(["pacman-key", "--delete", KEYID])


def show_banner(stdscr):
    stdscr.attron(curses.color_pair(1))
    for i, line in enumerate(BANNER.splitlines()):
        stdscr.addstr(i, 2, line)
    stdscr.attroff(curses.color_pair(1))


def draw_menu(stdscr, options, selected, status):
    stdscr.clear()
    show_banner(stdscr)
    y = 6
    stdscr.addstr(y, 2, f"Repository: {REPO}")
    stdscr.addstr(y + 1, 2, f"Server: {SERVER}")
    stdscr.addstr(y + 2, 2, f"Key: {KEYID}")
    stdscr.addstr(y + 4, 2, f"Repo status: {status}", curses.A_BOLD)
    stdscr.addstr(y + 6, 2, "Use arrow keys to move, Enter to select, q to quit:")
    for i, opt in enumerate(options):
        if i == selected:
            stdscr.addstr(y + 8 + i, 2, f"  > {opt}  ", curses.A_REVERSE)
        else:
            stdscr.addstr(y + 8 + i, 2, f"    {opt}")
    stdscr.refresh()


def curses_main(stdscr):
    curses.curs_set(0)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)

    while True:
        installed = repo_installed()
        outdated = installed and repo_outdated()
        if installed:
            options = ["Uninstall repo"]
            if outdated:
                options.append("Update repo")
            options.append("Quit")
            status = "INSTALLED" + (" (update available)" if outdated else "")
        else:
            options = ["Install repo", "Quit"]
            status = "NOT INSTALLED"

        selected = 0
        while True:
            draw_menu(stdscr, options, selected, status)
            key = stdscr.getch()
            if key == ord("q"):
                return
            if key in (curses.KEY_UP, ord("k")):
                selected = (selected - 1) % len(options)
            elif key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % len(options)
            elif key in (10, 13, curses.KEY_ENTER):
                break

        action = options[selected]
        if action == "Quit":
            return
        stdscr.clear()
        stdscr.addstr(0, 2, f"== {action} ...")
        stdscr.refresh()
        curses.endwin()
        if action == "Install repo":
            install_repo()
        elif action == "Uninstall repo":
            uninstall_repo()
        elif action == "Update repo":
            update_repo()
        input("Press Enter to continue...")
        curses.doupdate()


def main():
    if os.geteuid() != 0:
        print("Please run as root (sudo).", file=sys.stderr)
        sys.exit(1)
    try:
        import curses
        curses.wrapper(curses_main)
    except Exception as e:
        # no tty: non-interactive fallback
        print(f"No interactive terminal ({e}); installing repo automatically.")
        install_repo()


if __name__ == "__main__":
    main()
