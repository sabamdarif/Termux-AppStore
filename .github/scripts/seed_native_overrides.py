#!/usr/bin/env python3
"""One-time seeder: migrate repo-native apps/ entries into data/native-overrides.json.

Walks apps/<Folder>/, selects native entries whose install.sh body is a plain
single-package ``package_install_and_check`` call (no downloads/custom steps),
and emits an override entry keyed by ``package_name`` carrying the hand-written
app_name/folder casing/description/categories/run_cmd so the generated native
catalog preserves them exactly.

Terminal-only exceptions get ``terminal: true``. Apps whose packages are not in
any current Termux repo (KEEP_NO_REPO) are reported but skipped — they stay as
curated apps/ entries.

Usage: python3 .github/scripts/seed_native_overrides.py [--check]
  --check  only print the classification, don't write the file.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPS_DIR = ROOT / "apps"
OUT_FILE = ROOT / "data" / "native-overrides.json"

# Terminal-only apps that stay in the store via terminal:true (maintainer decision).
TERMINAL_PKGS = {
    "lazygit",
    "yazi",
    "neovim",
    "msedit",
    "fastfetch",
    "neofetch",
    "rclone",
}

# Dropped entirely: no meaningful run_cmd, base tool (maintainer decision).
DROP_PKGS = {"git"}

# Native apps with custom install bodies — detected structurally below, listed
# here only for the audit report.
KNOWN_CUSTOM = {
    "Extension-manager",
    "Linuxthemestore",
    "Nvchad",
    "Obs-studio",
    "Refine",
    "Termux-dm",
    "WaifuDownloader",
    "ytdlp-gui",
}

# Verified absent from main/x11/tur aarch64 Packages — stay as curated apps/.
KEEP_NO_REPO = {"Hexchat", "Leafpad", "Quassel"}

# Bodies containing any of these are custom installs, not plain repo installs.
CUSTOM_BODY_RE = re.compile(
    r"download_file|install_deb|install_appimage|install_archive|https?://"
    r"|create_desktop_entry|pd_package|distro_run|wget |curl |aria2c ",
    re.IGNORECASE,
)

META_KEYS = ("package_name", "run_cmd", "supported_arch", "version", "app_type")


def read_metadata_file(app_dir, stem):
    """Read <stem>.txt or <stem> (both spellings exist in apps/)."""
    for name in (f"{stem}.txt", stem):
        p = app_dir / name
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace").strip()
    return None


def parse_install_header(text):
    """Parse key=value assignments near the top of install.sh (ignores comments)."""
    meta = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^([a-z_]+)=(.*)$", stripped)
        if m and m.group(1) in META_KEYS:
            meta[m.group(1)] = m.group(2).strip().strip("\"'")
    return meta


def classify(app_dir):
    """Return (kind, meta) where kind is distro/custom/drop/plain/norepo."""
    folder = app_dir.name
    install = app_dir / "install.sh"
    if not install.is_file():
        return "custom", {}
    text = install.read_text(encoding="utf-8", errors="replace")
    meta = parse_install_header(text)
    if meta.get("app_type") == "distro":
        return "distro", meta
    if folder in KEEP_NO_REPO:
        return "norepo", meta
    pkg = meta.get("package_name", "")
    if pkg in DROP_PKGS:
        return "drop", meta
    if CUSTOM_BODY_RE.search(text):
        return "custom", meta
    if "package_install_and_check" not in text:
        return "custom", meta
    return "plain", meta


def main():
    check_only = "--check" in sys.argv
    packages = {}
    report = {"plain": [], "custom": [], "distro": [], "drop": [], "norepo": []}

    for app_dir in sorted(APPS_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not app_dir.is_dir():
            continue
        kind, meta = classify(app_dir)
        report[kind].append(app_dir.name)
        if kind != "plain":
            continue

        pkg = meta.get("package_name")
        if not pkg:
            print(f"WARNING: {app_dir.name} has no package_name, skipping")
            continue

        description = read_metadata_file(app_dir, "description")
        categories_raw = read_metadata_file(app_dir, "category")
        categories = (
            [c.strip() for c in categories_raw.split(",") if c.strip()]
            if categories_raw
            else []
        )

        entry: dict = {
            "app_name": app_dir.name.replace("-", " "),
            "folder_name": app_dir.name,
        }
        if description:
            entry["description"] = description
        if categories:
            entry["categories"] = categories
        entry["run_cmd"] = meta.get("run_cmd") or pkg
        if pkg in TERMINAL_PKGS:
            entry["terminal"] = True

        packages[pkg] = entry

    out = {"version": 1, "packages": dict(sorted(packages.items())), "exclude": []}

    for kind in ("plain", "custom", "distro", "drop", "norepo"):
        print(f"{kind}: {len(report[kind])}")
        if kind != "plain":
            for name in report[kind]:
                print(f"  {name}")

    if check_only:
        print(f"\n(check only) would write {len(packages)} overrides")
        return

    OUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {OUT_FILE} with {len(packages)} package overrides")


if __name__ == "__main__":
    main()
