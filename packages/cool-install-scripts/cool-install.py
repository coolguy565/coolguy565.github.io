#!/usr/bin/env python3
# Cool Arch installer - built on archinstall's Python API (archinstall >= 4.x).
# Run from the Arch ISO as root.
# Usage: curl -fsSL https://coolguy565.github.io/quick-install | bash
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from archinstall.lib.disk.device_handler import device_handler
from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.installer import Installer
from archinstall.lib.models.bootloader import Bootloader
from archinstall.lib.models.device import (
    DeviceModification,
    DiskLayoutConfiguration,
    DiskLayoutType,
    FilesystemType,
    ModificationStatus,
    PartitionFlag,
    PartitionModification,
    PartitionType,
    Size,
    SubvolumeModification,
    Unit,
)
from archinstall.lib.models.locale import LocaleConfiguration
from archinstall.lib.models.users import Password, User

REPO_NAME = "coolguy565"
REPO_KEY = "E36138CC5F015492A1D620581C4F28ACC1A18345"
REPO_URL = "https://github.com/coolguy565/coolguy565.github.io/releases/download/coolguy565"

# installed after the base system (base/sudo/linux-firmware are handled by archinstall)
PACKAGES = [
    "base-devel", "linux-cool-headers", "btrfs-progs",
    "hyprland", "waybar", "hyprpaper", "hypridle", "hyprshutdown",
    "walker", "foot", "mako", "thunar", "networkmanager",
    "git", "zsh", "curl", "figlet", "cool-install-scripts",
]

BANNER = """   ______            __   ___              __
  / ____/___  ____  / /  /   |  __________/ /_
 / /   / __ \\/ __ \\/ /  / /| | / ___/ ___/ __ \\
/ /___/ /_/ / /_/ / /  / ___ |/ /  / /__/ / / /
\\____/\\____/\\____/_/  /_/  |_/_/   \\___/_/ /_/"""


def figlet(text: str) -> None:
    if shutil.which("figlet"):
        subprocess.run(["figlet", "-f", "slant", text])
    else:
        print(BANNER)


def ask(prompt: str, default: str = "") -> str:
    ans = input(f"  {prompt} [{default}]: ").strip()
    return ans or default


def ask_num(prompt: str) -> str:
    return input(f"  {prompt}: ").strip()


def confirm(prompt: str) -> bool:
    return input(f"  {prompt} [y/N]: ").strip().lower() == "y"


def run(cmd: list[str], check: bool = True) -> None:
    subprocess.run(cmd, check=check)


def bootloader_value(name: str) -> Bootloader:
    """Resolve a bootloader from its enum name, tolerant of naming drift."""
    for cand in (name, name.upper(), name.lower(), "Systemd" if name == "systemd-boot" else None):
        if cand is None:
            continue
        if (b := getattr(Bootloader, cand, None)) is not None:
            return b
    raise ValueError(f"Unknown bootloader: {name}")


def key_input() -> str:
    """Read a single key from the real terminal (works even when piped)."""
    import termios
    import tty
    fd = os.open("/dev/tty", os.O_RDWR)
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        ch = os.read(fd, 1)
        if ch == b"\x1b":
            rest = os.read(fd, 2)
            if rest == b"[C":
                return "right"
            if rest == b"[D":
                return "left"
            if rest == b"[A":
                return "up"
            if rest == b"[B":
                return "down"
            return "esc"
        if ch in (b"\r", b"\n"):
            return "enter"
        return ch.decode(errors="ignore")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        os.close(fd)


def size_slider(default: int, step: int, minv: int, maxv: int) -> int:
    size = max(minv, min(default, maxv))
    width = 40
    while True:
        filled = size * width // maxv
        sys.stdout.write(
            f"\r  Cool Arch size: {size:4d} GB  [{'=' * filled}{'-' * (width - filled)}]"
            f"  \033[33m<-\033[0m/\033[33m->\033[0m change  \033[32mEnter\033[0m confirm\033[K"
        )
        sys.stdout.flush()
        k = key_input()
        if k == "left":
            size = max(minv, size - step)
        elif k == "right":
            size = min(maxv, size + step)
        elif k == "enter":
            print()
            return size


def host_setup_repo() -> None:
    """XferCommand HTTP/1.1 fix + add coolguy565 repo + trust key on the HOST.

    Must run before archinstall pacstraps, so linux-cool (from our repo) resolves
    and downloads don't hit GitHub's curl error 63 on HTTP/2.
    """
    conf = Path("/etc/pacman.conf")
    conf_text = conf.read_text()
    if "XferCommand" not in conf_text:
        with conf.open("a") as f:
            f.write("XferCommand = /usr/bin/curl --http1.1 -L -C - -f -o %o %u\n")
        conf_text = conf.read_text()
    if f"[{REPO_NAME}]" not in conf_text:
        with conf.open("a") as f:
            f.write(f"\n[{REPO_NAME}]\nSigLevel = Required DatabaseOptional\nServer = {REPO_URL}\n")
        asc = "/tmp/cool.asc"
        urllib.request.urlretrieve(f"{REPO_URL}/{REPO_NAME}.asc", asc)
        run(["pacman-key", "--add", asc])
        run(["pacman-key", "--lsign-key", REPO_KEY])
        os.unlink(asc)
    run(["pacman", "-Syy"])


def internet_ok() -> bool:
    try:
        subprocess.run(
            ["ping", "-c1", "-W3", "ping.archlinux.org"],
            capture_output=True, check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def main() -> None:
    if os.geteuid() != 0:
        print("Please run as root.", file=sys.stderr)
        sys.exit(1)

    # ---------- 1. banner ----------
    figlet("Cool Arch")

    # ---------- 2. language / keyboard ----------
    print("== Language")
    langs = {
        "1": ("us", "", "en_US.UTF-8", "English (US)"),
        "2": ("br", "abnt2", "pt_BR.UTF-8", "Portuguese (BR)"),
        "3": ("de", "", "de_DE.UTF-8", "German"),
        "4": ("fr", "", "fr_FR.UTF-8", "French"),
        "5": ("es", "", "es_ES.UTF-8", "Spanish"),
    }
    for k, (_, _, _, name) in langs.items():
        print(f"  {k}) {name}")
    kb_layout, kb_variant, locale, _ = langs.get(ask_num("Choice [1]") or "1", langs["1"])

    # ---------- 3. caps option ----------
    print("== Caps Lock behavior")
    print("  1) Caps --> Caps\n  2) Caps --> Compose\n  3) Caps --> Ctrl")
    caps = {"1": "", "2": "compose:caps", "3": "ctrl:nocaps"}.get(ask_num("Choice [1]") or "1", "")

    # ---------- 4. resolution ----------
    res = ask("Screen resolution (blank = auto)", "1920x1080")
    hz = ask("Refresh rate (blank = default)", "")
    if not res or res == "auto":
        mode = "preferred"
    else:
        mode = f"{res}@{hz}" if hz else res

    # ---------- 5. user / password ----------
    while True:
        username = ask("Username", "")
        if username:
            break
    while True:
        p1 = ask_num("Password")
        p2 = ask_num("Confirm password")
        if p1 and p1 == p2:
            break
        print("  Passwords do not match or empty.")

    # ---------- 5b. hostname / timezone / DM / browser ----------
    hostname = ask("Hostname", "coolarch")
    tz_map = {
        "1": "Etc/UTC",
        "2": "America/Sao_Paulo",
        "3": "America/New_York",
        "4": "Europe/London",
        "5": "Europe/Berlin",
        "6": "Asia/Tokyo",
        "7": ask("Timezone (e.g. America/Sao_Paulo)", "Etc/UTC"),
    }
    print("== Timezone")
    for k, v in tz_map.items():
        print(f"  {k}) {v}")
    timezone = tz_map.get(ask_num("Choice [1]") or "1", "Etc/UTC")

    print("== Display manager\n  1) SDDM\n  2) None")
    dm = "sddm" if (ask_num("Choice [1]") or "1") == "1" else "none"

    print("== Browser")
    browsers = {
        "1": "google-chrome", "2": "firefox", "3": "librewolf-bin",
        "4": "chromium", "5": "brave-bin",
    }
    for k, v in browsers.items():
        print(f"  {k}) {v}")
    browser = browsers.get(ask_num("Choice [2]") or "2", "firefox")

    # ---------- 6. disk selection + OS detection ----------
    print("== Available disks:")
    run(["lsblk", "-d", "-o", "NAME,SIZE,MODEL", "-n"])
    disk = ask("Target disk (e.g. nvme0n1, sda)", "")
    dev = Path(f"/dev/{disk}")
    if not dev.is_block_device():
        print(f"Not a block device: {dev}", file=sys.stderr)
        sys.exit(1)

    disk_gb = int(subprocess.check_output(
        ["lsblk", "-b", "-d", "-n", "-o", "SIZE", str(dev)]).split()[0]) // 1073741824
    print(f"  Disk size: {disk_gb} GB")

    parts = subprocess.check_output(
        ["lsblk", "-n", "-o", "NAME", str(dev)], text=True).splitlines()
    parts = [p for p in parts if p != disk]

    print("\n== Detecting installed OSes (os-prober)")
    try:
        run(["pacman", "-S", "--noconfirm", "os-prober"], check=False)
    except subprocess.CalledProcessError:
        pass
    windows_found = False
    os_prober_found = False
    if shutil.which("os-prober"):
        try:
            osprober_out = subprocess.check_output(["os-prober"], text=True).strip()
        except subprocess.CalledProcessError:
            osprober_out = ""
        for line in osprober_out.splitlines():
            os_prober_found = True
            fields = line.split(":")
            osname = fields[2] if len(fields) > 2 else line
            print(f"    found: {osname} on {fields[0]}")
            if "windows" in line.lower():
                windows_found = True
    if not os_prober_found:
        print("    no other OS detected by os-prober")
    if not parts:
        print("\n== No existing partitions on the target - full disk install")
        MODE = "erase"
    else:
        print("\n== An existing OS/partitions were found on /dev/" + disk)
        if windows_found:
            print("  (Windows detected - it will appear in the boot menu)")
        print("  1) Install alongside the existing OS")
        print("  2) Erase disk and install Cool Arch Linux")
        MODE = "alongside" if (ask_num("Choice [1]") or "1") == "1" else "erase"

    if MODE == "alongside":
        print("== Alongside install: this will shrink the largest ext4 partition on /dev/" + disk)
        if not confirm("Proceed?"):
            sys.exit(1)
    else:
        if not confirm(f"WARNING: this ERASES everything on /dev/{disk}. Continue?"):
            sys.exit(1)
        if windows_found:
            if not confirm("FINAL WARNING: Windows was detected on this disk and WILL BE DESTROYED. Continue?"):
                sys.exit(1)

    # ---------- 7. alongside size selection ----------
    if MODE == "alongside":
        print(f"== Shrinking largest ext4/ntfs partition on /dev/{disk}")
        print(f"  Select how much of the disk Cool Arch should use (max {disk_gb} GB).")
        grow = size_slider(100, 5, 20, disk_gb)
        if grow >= disk_gb:
            print("  Full disk selected - switching to erase install.")
            MODE = "erase"

    # ---------- 8. install summary ----------
    is_uefi = Path("/sys/firmware/efi").is_dir()
    if is_uefi:
        print("== Bootloader (UEFI)\n  1) GRUB\n  2) systemd-boot\n  3) Limine")
        bl_name = {"2": "systemd-boot", "3": "Limine"}.get(ask_num("Choice [1]") or "1", "GRUB")
    else:
        print("== Bootloader (BIOS)\n  1) GRUB\n  2) Limine")
        bl_name = {"2": "Limine"}.get(ask_num("Choice [1]") or "1", "GRUB")
    bl = bootloader_value(bl_name)

    print("\n==================================================")
    print("  Cool Arch Linux - install summary")
    print("==================================================")
    print(f"  Language / keyboard : {kb_layout}{kb_variant}  (locale: {locale})")
    print(f"  Caps Lock behavior  : {caps or 'Caps --> Caps'}")
    print(f"  Resolution          : {mode}")
    print(f"  Username            : {username}")
    print(f"  Hostname            : {hostname}")
    print(f"  Timezone            : {timezone}")
    print(f"  Display manager     : {dm}")
    print(f"  Bootloader          : {bl_name} ({'UEFI' if is_uefi else 'BIOS'})")
    print(f"  Browser             : {browser}")
    print(f"  Target disk         : /dev/{disk} ({disk_gb} GB)")
    print(f"  Install mode        : {'ERASE disk and install Cool Arch Linux' if MODE == 'erase' else f'Alongside existing OS (Cool Arch gets {grow} GB)'}")
    if windows_found:
        print("  Note                : Windows detected (will appear in the boot menu)")
    print("==================================================")
    if not confirm("Start installation?"):
        print("Aborted.")
        sys.exit(1)

    # ---------- 9. repo + connectivity (host side, before pacstrap) ----------
    print("\n== Adding coolguy565 repo (host)")
    host_setup_repo()
    print("== Checking internet connectivity")
    if not internet_ok():
        print("ERROR: no internet connectivity. Fix networking and re-run.", file=sys.stderr)
        sys.exit(1)

    # ---------- 10. partition ----------
    print("== Partitioning /dev/" + disk)
    device = device_handler.get_device(dev)
    if not device:
        print("Not a block device.", file=sys.stderr)
        sys.exit(1)
    sector = device.device_info.sector_size

    if MODE == "erase":
        device_modification = DeviceModification(device, wipe=True)
        if is_uefi:
            device_modification.add_partition(PartitionModification(
                status=ModificationStatus.CREATE,
                type=PartitionType.PRIMARY,
                start=Size(1, Unit.MiB, sector),
                length=Size(1024, Unit.MiB, sector),
                mountpoint=Path("/boot"),
                fs_type=FilesystemType.FAT32,
                flags=[PartitionFlag.BOOT, PartitionFlag.ESP],
            ))
            root_start = Size(1025, Unit.MiB, sector)
        else:
            # BIOS/MBR: GRUB reads btrfs directly, /boot on a small FAT partition
            device_modification.add_partition(PartitionModification(
                status=ModificationStatus.CREATE,
                type=PartitionType.PRIMARY,
                start=Size(1, Unit.MiB, sector),
                length=Size(1024, Unit.MiB, sector),
                mountpoint=Path("/boot"),
                fs_type=FilesystemType.FAT32,
                flags=[PartitionFlag.BOOT],
            ))
            root_start = Size(1025, Unit.MiB, sector)
        device_modification.add_partition(PartitionModification(
            status=ModificationStatus.CREATE,
            type=PartitionType.PRIMARY,
            start=root_start,
            length=device.device_info.total_size - root_start,
            mountpoint=None,
            fs_type=FilesystemType.BTRFS,
            mount_options=["compress=zstd"],
            btrfs_subvols=[
                SubvolumeModification("@", Path("/")),
                SubvolumeModification("@home", Path("/home")),
            ],
        ))
    else:
        # alongside: shrink the largest ext4/ntfs partition, keep everything else
        rows = subprocess.check_output(
            ["lsblk", "-n", "-o", "NAME,FSTYPE,SIZE", "-r", str(dev)], text=True).splitlines()
        largest = None
        largest_size = 0
        largest_fs = ""
        for line in rows:
            name, fstype, size = line.split()
            if fstype not in ("ext4", "ntfs"):
                continue
            try:
                n = subprocess.check_output(
                    ["numfmt", "--from=iec", size], text=True).strip()
                size_bytes = int(n)
            except Exception:
                continue
            if size_bytes > largest_size:
                largest, largest_size, largest_fs = name, size_bytes, fstype
        if not largest:
            print("No ext4/ntfs partition to shrink! Alongside currently supports ext4 and NTFS.",
                  file=sys.stderr)
            sys.exit(1)
        largest_dev = Path(f"/dev/{largest}")
        print(f"  Shrinking {largest_dev} ({largest_fs}) to make {grow} GB for Cool Arch")
        if largest_fs == "ext4":
            run(["e2fsck", "-fy", str(largest_dev)])
            run(["resize2fs", str(largest_dev), f"{grow}G"])
        else:
            try:
                run(["ntfsresize", "-f", "--size", f"{grow}G", str(largest_dev)])
            except subprocess.CalledProcessError:
                print("ERROR: ntfsresize failed (install ntfs-3g on the ISO).", file=sys.stderr)
                sys.exit(1)
        # find the new end of the shrunk partition (in bytes)
        out = subprocess.check_output(
            ["parted", "-s", str(dev), "unit", "B", "print"], text=True)
        part_num = largest[len(disk):].lstrip("p")
        fs_new_end = 0
        for line in out.splitlines():
            f = line.split()
            if len(f) >= 3 and f[0] == part_num:
                start = int(f[1].rstrip("B"))
                end = int(f[2].rstrip("B"))
                fs_new_end = start + (end - start) - (grow * 1073741824)
        if not fs_new_end:
            print("ERROR: could not compute resized partition end.", file=sys.stderr)
            sys.exit(1)
        subprocess.run(["parted", "-s", str(dev), "resizepart", part_num, f"{fs_new_end}B"],
                       check=True)
        subprocess.run(["parted", "-s", str(dev), "mkpart", "COOL", "btrfs",
                        f"{fs_new_end // 1048576}MiB", "100%"], check=True)
        subprocess.run(["partprobe", str(dev)], check=False)

        device = device_handler.get_device(dev)
        if not device:
            print("Not a block device.", file=sys.stderr)
            sys.exit(1)
        # create only the new root partition; archinstall keeps the rest (wipe=False)
        root_part = PartitionModification(
            status=ModificationStatus.CREATE,
            type=PartitionType.PRIMARY,
            start=Size(fs_new_end, Unit.B, sector),
            length=device.device_info.total_size - Size(fs_new_end, Unit.B, sector),
            mountpoint=None,
            fs_type=FilesystemType.BTRFS,
            mount_options=["compress=zstd"],
            btrfs_subvols=[
                SubvolumeModification("@", Path("/")),
                SubvolumeModification("@home", Path("/home")),
            ],
        )
        device_modification = DeviceModification(device, wipe=False)
        device_modification.add_partition(root_part)

    disk_config = DiskLayoutConfiguration(
        config_type=DiskLayoutType.Btrfs,
        device_modifications=[device_modification],
    )

    fs_handler = FilesystemHandler(disk_config)
    fs_handler.perform_filesystem_operations()

    # ---------- 11. install (pacstrap + configure) ----------
    mountpoint = Path("/mnt/cool")

    with Installer(mountpoint, disk_config, kernels=["linux-cool"]) as installation:
        installation.mount_ordered_layout()
        installation.minimal_installation(
            hostname=hostname,
            locale_config=LocaleConfiguration(kb_layout=kb_layout, sys_lang=locale, sys_enc="UTF-8"),
        )
        installation.set_timezone(timezone)
        installation.set_keyboard_language(kb_layout)
        installation.add_bootloader(bl)
        installation.add_additional_packages(
            PACKAGES + [browser] + (["sddm"] if dm == "sddm" else [])
        )

        user = User(username, Password(plaintext=p1), True)
        installation.create_users(user)

        # ---------- 12. configure ----------
        # persist the coolguy565 repo + trust its key inside the new system
        target_conf = mountpoint / "etc/pacman.conf"
        tconf = target_conf.read_text()
        if f"[{REPO_NAME}]" not in tconf:
            with target_conf.open("a") as f:
                f.write(f"\n[{REPO_NAME}]\nSigLevel = Required DatabaseOptional\nServer = {REPO_URL}\n")
        asc = "/tmp/cool.asc"
        urllib.request.urlretrieve(f"{REPO_URL}/{REPO_NAME}.asc", asc)
        shutil.copy(asc, mountpoint / "tmp/cool.asc")
        os.unlink(asc)
        installation.arch_chroot("pacman-key --init")
        installation.arch_chroot("pacman-key --populate archlinux")
        installation.arch_chroot("pacman-key --add /tmp/cool.asc")
        installation.arch_chroot(f"pacman-key --lsign-key {REPO_KEY}")
        run(["rm", "-f", str(mountpoint / "tmp/cool.asc")])

        # services
        installation.arch_chroot("systemctl enable NetworkManager")
        if dm == "sddm":
            installation.arch_chroot("systemctl enable sddm")
            installation.arch_chroot("mkdir -p /etc/sddm.conf.d")
            installation.arch_chroot("echo '[Theme]' > /etc/sddm.conf.d/cool-theme.conf")
            installation.arch_chroot("echo 'Current=cool-arch' >> /etc/sddm.conf.d/cool-theme.conf")

        # zshrc for new users (auto-start Hyprland on the bare console when no DM)
        skel_zshrc = mountpoint / "etc/skel/.zshrc"
        if dm == "none":
            skel_zshrc.write_text(
                "# Cool Arch: auto-start Hyprland when logging in at the real console (tty1),\n"
                "# but not inside a pty (terminal emulator, SSH, etc.)\n"
                'if [[ "$(tty)" == "/dev/tty1" ]] && [[ "$(tty)" != /dev/pts/* ]]; then\n'
                "  exec start-hyprland\n"
                "fi\n"
            )
        else:
            skel_zshrc.write_text("")

        # ---------- 13. certificate fix script (optional) ----------
        print("\n== Certificate fix script (optional)")
        print("  If the system has a broken CA certificate setup, paste a script URL")
        print("  that repairs it. It will run inside the chroot as:")
        print("    curl -k <url> | bash")
        print("  (curl -k bypasses cert verification so it works even with no CA certs)")
        cert_url = ask("Certificate script URL (ENTER to skip)", "")
        if cert_url:
            print(f"  Running in chroot: curl -k {cert_url} | bash")
            installation.arch_chroot(
                f"bash -c {shlex.quote(f'curl -k {shlex.quote(cert_url)} | bash')}"
            )
            print("  Certificate script finished.")
        else:
            print("  Skipped certificate fix.")

        # ---------- 14. cool-arch configs ----------
        skel = mountpoint / "etc/skel/.config"
        for d in ("hypr", "waybar", "walker"):
            (skel / d).mkdir(parents=True, exist_ok=True)
        for src, dst in [
            ("hypr/hyprland.lua", "hypr/hyprland.lua"),
            ("hypr/hyprpaper.conf", "hypr/hyprpaper.conf"),
            ("waybar/config.jsonc", "waybar/config.jsonc"),
            ("waybar/style.css", "waybar/style.css"),
            ("walker/config.toml", "walker/config.toml"),
        ]:
            # cool-install-scripts was installed into the target by add_additional_packages
            target = skel / dst
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(mountpoint / f"usr/share/cool-arch/{src}", target)
        # apply selections to the skel hyprland.lua
        hconf = (skel / "hypr/hyprland.lua").read_text()
        hconf = hconf.replace("{{MONITOR_MODE}}", mode)
        hconf = hconf.replace("{{KEYBOARD_LAYOUT}}", kb_layout)
        hconf = hconf.replace("{{CAPS_OPTION}}", caps)
        (skel / "hypr/hyprland.lua").write_text(hconf)
        # populate the new user from skel and give them ownership
        subprocess.run(["cp", "-a", f"{mountpoint}/etc/skel/.", f"{mountpoint}/home/{username}/"],
                       check=True)
        installation.arch_chroot(f"chown -R {username}:{username} /home/{username}")

        # ---------- 15. bootloader extras ----------
        # GRUB: show other OSes (alongside) and keep archinstall's btrfs kernel args
        if bl == bootloader_value("GRUB") and MODE == "alongside":
            grub_default = mountpoint / "etc/default/grub"
            gconf = grub_default.read_text()
            gconf = re.sub(r"^#\s*GRUB_DISABLE_OS_PROBER=false", "GRUB_DISABLE_OS_PROBER=false",
                           gconf, count=1, flags=re.MULTILINE)
            if "GRUB_DISABLE_OS_PROBER=false" not in gconf:
                gconf += "\nGRUB_DISABLE_OS_PROBER=false\n"
            grub_default.write_text(gconf)
            installation.arch_chroot("grub-mkconfig -o /boot/grub/grub.cfg")

        # Secure Boot + TPM2 (UEFI only): shim + sbctl keys
        if is_uefi:
            print("\n== Secure Boot + TPM2")
            print("  Sets up shim + sbctl keys and installs TPM2 tools.")
            print("  NOTE: key enrollment needs the firmware in Setup Mode (or Secure Boot disabled).")
            if confirm("Set up Secure Boot and TPM2?"):
                installation.arch_chroot("pacman -S --noconfirm sbctl shim-signed tpm2-tools tpm2-tss")
                try:
                    installation.arch_chroot("systemctl enable tpm2.target")
                except Exception:
                    pass
                installation.arch_chroot("sbctl create-keys")
                try:
                    status = installation.arch_chroot("sbctl status").decode(errors="ignore").lower()
                except Exception:
                    status = ""
                if "setup mode: enabled" in status:
                    try:
                        installation.arch_chroot("sbctl enroll-keys --microsoft")
                        print("  Enrolled Cool Arch + Microsoft keys.")
                    except Exception:
                        print("  WARNING: key enrollment failed.")
                    # sign the boot chain
                    print("  == Signing boot files with sbctl")
                    for kernel in ("vmlinuz-linux-cool",):
                        installation.arch_chroot(f"sbctl sign /boot/{kernel}")
                    for img in (mountpoint / "boot").glob("initramfs-*.img"):
                        installation.arch_chroot(f"sbctl sign /boot/{img.name}")
                else:
                    print("  Not in Setup Mode - relying on the Microsoft-signed shim chain.")
                    print("  (If it fails to boot, disable Secure Boot or enroll keys from firmware settings.)")

        installation.genfstab()

    # ---------- 16. done ----------
    figlet("Done!")
    print("Cool Arch Linux installed.")
    if confirm("Reboot now?"):
        subprocess.run(["umount", "-R", "/mnt/cool"], check=False)
        run(["reboot"])


if __name__ == "__main__":
    main()
