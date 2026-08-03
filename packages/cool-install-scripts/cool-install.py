#!/usr/bin/env python3
# Cool Arch installer - built on archinstall's Python API.
# Run from the Arch ISO as root.
import shutil
import subprocess
import sys
from pathlib import Path

from archinstall.default_profiles.minimal import MinimalProfile
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
    Unit,
)
from archinstall.lib.models.profile import ProfileConfiguration
from archinstall.lib.models.users import Password, User
from archinstall.lib.profile.profiles_handler import profile_handler

REPO_NAME = "coolguy565"
REPO_KEY = "E36138CC5F015492A1D620581C4F28ACC1A18345"
REPO_URL = "https://github.com/coolguy565/coolguy565.github.io/releases/download/coolguy565"
PACKAGES = [
    "linux-cool", "linux-cool-headers", "btrfs-progs",
    "hyprland", "waybar", "hyprpaper", "hypridle", "hyprshutdown",
    "walker", "foot", "mako", "thunar", "networkmanager",
    "sudo", "git", "zsh", "curl", "figlet", "cool-install-scripts",
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


def main() -> None:
    if os_geteuid() != 0:
        print("Please run as root.", file=sys.stderr)
        sys.exit(1)

    # ---- banner ----
    figlet("Cool Arch")

    # ---- language ----
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

    # ---- caps ----
    print("== Caps Lock behavior")
    print("  1) Caps --> Caps\n  2) Caps --> Compose\n  3) Caps --> Ctrl")
    caps = {"1": "", "2": "compose:caps", "3": "ctrl:nocaps"}.get(ask_num("Choice [1]") or "1", "")

    # ---- resolution ----
    res = ask("Screen resolution (blank = auto)", "1920x1080")
    hz = ask("Refresh rate (blank = default)", "")
    if not res or res == "auto":
        mode = "preferred"
    else:
        mode = f"{res}@{hz}" if hz else res

    # ---- user / password ----
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

    # ---- hostname / timezone ----
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

    # ---- display manager ----
    print("== Display manager\n  1) SDDM\n  2) None")
    dm = "sddm" if (ask_num("Choice [1]") or "1") == "1" else "none"

    # ---- browser ----
    print("== Browser")
    browsers = {
        "1": "google-chrome", "2": "firefox", "3": "librewolf-bin",
        "4": "chromium", "5": "brave-bin",
    }
    for k, v in browsers.items():
        print(f"  {k}) {v}")
    browser = browsers.get(ask_num("Choice [2]") or "2", "firefox")

    # ---- disk ----
    print("== Available disks:")
    run(["lsblk", "-d", "-o", "NAME,SIZE,MODEL", "-n"])
    dev = ask_num("Target disk (e.g. vda, sda)")
    device = device_handler.get_device(Path(f"/dev/{dev}"))
    if not device:
        print("Not a block device.", file=sys.stderr)
        sys.exit(1)

    # ---- bootloader ----
    is_uefi = Path("/sys/firmware/efi").is_dir()
    if is_uefi:
        print("== Bootloader (UEFI)\n  1) GRUB\n  2) systemd-boot\n  3) Limine")
        bl = {"1": Bootloader.GRUB, "2": Bootloader.SystemdBoot, "3": Bootloader.Limine}.get(
            ask_num("Choice [1]") or "1", Bootloader.GRUB)
    else:
        print("== Bootloader (BIOS)\n  1) GRUB\n  2) Limine")
        bl = {"2": Bootloader.Limine}.get(ask_num("Choice [1]") or "1", Bootloader.GRUB)

    # ---- summary ----
    print("\n== Cool Arch install summary")
    print(f"  Language: {kb_layout}{kb_variant}")
    print(f"  Caps: {caps or 'Caps --> Caps'}")
    print(f"  Resolution: {mode}")
    print(f"  Username: {username}")
    print(f"  Hostname: {hostname}")
    print(f"  Timezone: {timezone}")
    print(f"  Display manager: {dm}")
    print(f"  Browser: {browser}")
    print(f"  Bootloader: {bl.value if hasattr(bl, 'value') else bl} ({'UEFI' if is_uefi else 'BIOS'})")
    print(f"  Target disk: /dev/{dev}")
    if not confirm("Start installation?"):
        print("Aborted.")
        sys.exit(1)

    # ---- erase: let archinstall partition (Btrfs @/@home layout) ----
    device_modification = DeviceModification(device, wipe=True)

    boot = PartitionModification(
        status=ModificationStatus.CREATE,
        type=PartitionType.PRIMARY,
        start=Size(1, Unit.MiB, device.device_info.sector_size),
        length=Size(1024, Unit.MiB, device.device_info.sector_size),
        mountpoint=Path("/boot"),
        fs_type=FilesystemType.FAT32,
        flags=[PartitionFlag.BOOT],
    )
    device_modification.add_partition(boot)

    root = PartitionModification(
        status=ModificationStatus.CREATE,
        type=PartitionType.PRIMARY,
        start=Size(1025, Unit.MiB, device.device_info.sector_size),
        length=device.device_info.total_size - Size(1025, Unit.MiB, device.device_info.sector_size),
        mountpoint=None,
        fs_type=FilesystemType.BTRFS,
    )
    device_modification.add_partition(root)

    disk_config = DiskLayoutConfiguration(
        config_type=DiskLayoutType.Btrfs,
        device_modifications=[device_modification],
    )

    fs_handler = FilesystemHandler(disk_config)
    fs_handler.perform_filesystem_operations()

    mountpoint = Path("/mnt/cool")

    with Installer(mountpoint, disk_config, kernels=["linux-cool"]) as installation:
        installation.mount_ordered_layout()
        installation.minimal_installation(hostname=hostname, locale=locale)
        installation.set_timezone(timezone)
        installation.set_keyboard_language(kb_layout)
        installation.add_bootloader(bl)
        installation.add_additional_packages(PACKAGES + [browser] + (["sddm"] if dm == "sddm" else []))

        user = User(username, Password(plaintext=p1), True)
        installation.create_users(user)

        # ---- Cool Arch post-install ----
        installation.run_arch_chroot("pacman -Syy --noconfirm")
        installation.run_arch_chroot("systemctl enable NetworkManager")
        if dm == "sddm":
            installation.run_arch_chroot("systemctl enable sddm")
            installation.run_arch_chroot("mkdir -p /etc/sddm.conf.d")
            installation.run_arch_chroot("echo '[Theme]' > /etc/sddm.conf.d/cool-theme.conf")
            installation.run_arch_chroot("echo 'Current=cool-arch' >> /etc/sddm.conf.d/cool-theme.conf")

        # apply configs to the new user
        home = f"/home/{username}"
        installation.run_arch_chroot(f"mkdir -p {home}/.config/hypr {home}/.config/waybar {home}/.config/walker")
        for src, dst in [
            ("/usr/share/cool-arch/hypr/hyprland.lua", f"{home}/.config/hypr/hyprland.lua"),
            ("/usr/share/cool-arch/hypr/hyprpaper.conf", f"{home}/.config/hypr/hyprpaper.conf"),
            ("/usr/share/cool-arch/waybar/config.jsonc", f"{home}/.config/waybar/config.jsonc"),
            ("/usr/share/cool-arch/waybar/style.css", f"{home}/.config/waybar/style.css"),
            ("/usr/share/cool-arch/walker/config.toml", f"{home}/.config/walker/config.toml"),
        ]:
            installation.run_arch_chroot(f"install -Dm644 {src} {dst}")

        # apply selections to hyprland.lua
        installation.run_arch_chroot(f"sed -i 's/{{{{MONITOR_MODE}}}}/{mode}/' {home}/.config/hypr/hyprland.lua")
        installation.run_arch_chroot(f"sed -i 's/{{{{KEYBOARD_LAYOUT}}}}/{kb_layout}/' {home}/.config/hypr/hyprland.lua")
        installation.run_arch_chroot(f"sed -i 's/{{{{CAPS_OPTION}}}}/{caps}/' {home}/.config/hypr/hyprland.lua")
        installation.run_arch_chroot(f"chown -R {username}:{username} {home}/.config")

        installation.genfstab()

    figlet("Done!")
    print("Cool Arch Linux installed.")
    if confirm("Reboot now?"):
        run(["reboot"])


def os_geteuid():
    import os
    return os.geteuid()


if __name__ == "__main__":
    main()
