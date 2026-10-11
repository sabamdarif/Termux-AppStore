# SPDX-License-Identifier: GPL-3.0-or-later
"""Native repo catalog — download, cache, and merge the CI-generated data.

The daily `native-catalog` workflow publishes per-repo/arch JSON catalogs plus
an icon pack on the rolling ``native_data`` release. This module fetches the
catalogs matching the device's enabled Termux repos, merges them under the
curated ``apps.json`` (curated wins), and keeps the native icons in sync.
"""

import glob
import json
import os
import shutil
import subprocess
import zipfile
from urllib.request import Request, urlopen

from termux_appstore.constants import (
    APPSTORE_LOGO_DIR,
    NATIVE_DATA_BASE,
    NATIVE_DIR,
    NATIVE_REPOS,
    TERMUX_PREFIX,
)

# Set by enabled_native_repos(); read by the window after refresh to show the
# "enable x11-repo" warning once per refresh.
LAST_X11_MISSING = False

USER_AGENT = "termux-appstore/native-data"


def detect_package_manager():
    """Return ``"apt"`` or ``"pacman"`` for this Termux installation."""
    try:
        cmd = (
            f"source {TERMUX_PREFIX}/bin/termux-setup-package-manager "
            "&& echo $TERMUX_APP_PACKAGE_MANAGER"
        )
        result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
        pm = result.stdout.strip()
        if pm in ("apt", "pacman"):
            return pm
    except Exception:
        pass
    return "pacman" if shutil.which("pacman") else "apt"


def enabled_repos_apt(prefix=TERMUX_PREFIX):
    """Detect enabled repos from apt sources. Returns e.g. {"x11", "tur"}."""
    repos = set()
    files = [os.path.join(prefix, "etc", "apt", "sources.list")]
    files += sorted(
        glob.glob(os.path.join(prefix, "etc", "apt", "sources.list.d", "*.list"))
    )
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "termux-x11" in line or " x11 " in f" {line} ":
                repos.add("x11")
            if "tur.kcubeterm" in line or "tur-packages" in line:
                repos.add("tur")
    return repos


def enabled_repos_pacman(prefix=TERMUX_PREFIX):
    """Detect enabled repos from pacman.conf uncommented [sections]."""
    repos = set()
    path = os.path.join(prefix, "etc", "pacman.conf")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return repos
    for line in lines:
        line = line.strip()
        if line.startswith("#") or not (line.startswith("[") and line.endswith("]")):
            continue
        section = line[1:-1].strip().lower()
        if section in ("x11", "tur"):
            repos.add(section)
    return repos


def enabled_native_repos():
    """Return ``(repos: set[str], x11_missing: bool)`` for this device."""
    global LAST_X11_MISSING
    if detect_package_manager() == "pacman":
        repos = enabled_repos_pacman()
    else:
        repos = enabled_repos_apt()
    LAST_X11_MISSING = "x11" not in repos
    return repos & set(NATIVE_REPOS), LAST_X11_MISSING


def _fetch_json(url, timeout=60):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_native_catalogs(repos):
    """Download + cache the native catalogs for *repos*.

    Catalogs are one file per repo (``x11.json`` etc.); each entry's
    ``supported_arch`` field records the arches it is available on, and the
    app's existing arch filter in ``load_app_metadata`` consumes that. On
    download failure the cached copy is used; a repo with neither is skipped.
    Returns a flat list of entries.
    """
    os.makedirs(NATIVE_DIR, exist_ok=True)
    # The main-repo catalog (terminal exceptions, VLC-style entries) is always
    # fetched: the main repo is enabled on every Termux install.
    repos = set(repos) | {"main"}
    entries = []
    for repo in sorted(repos):
        cache = os.path.join(NATIVE_DIR, f"{repo}.json")
        try:
            data = _fetch_json(f"{NATIVE_DATA_BASE}/{repo}.json")
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(data, f)
            entries.extend(data)
            print(f"native catalog {repo}: {len(data)} entries (fresh)")
        except Exception as e:
            print(f"native catalog {repo} download failed: {e}")
            if os.path.exists(cache):
                try:
                    with open(cache, encoding="utf-8") as f:
                        data = json.load(f)
                    entries.extend(data)
                    print(f"native catalog {repo}: {len(data)} entries (cached)")
                except Exception as e2:
                    print(f"cached catalog unreadable: {e2}")
    return entries


def sync_native_icons():
    """Download native-icons.zip when the catalog version changed.

    Must run AFTER the curated logos.zip extraction in the refresh pipeline —
    that step wipes APPSTORE_LOGO_DIR (P8).
    """
    os.makedirs(NATIVE_DIR, exist_ok=True)
    marker = os.path.join(NATIVE_DIR, "icons-version")
    try:
        info = _fetch_json(f"{NATIVE_DATA_BASE}/native-version.json", timeout=30)
        version = str(info.get("catalog_version", ""))
    except Exception as e:
        print(f"native-version.json unavailable: {e}")
        return
    if not version:
        return
    try:
        with open(marker) as f:
            if f.read().strip() == version:
                return
    except OSError:
        pass
    zip_path = os.path.join(NATIVE_DIR, "native-icons.zip")
    try:
        req = Request(
            f"{NATIVE_DATA_BASE}/native-icons.zip",
            headers={"User-Agent": USER_AGENT},
        )
        with urlopen(req, timeout=300) as resp, open(zip_path, "wb") as f:
            shutil.copyfileobj(resp, f)
        os.makedirs(APPSTORE_LOGO_DIR, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(APPSTORE_LOGO_DIR)
        with open(marker, "w") as f:
            f.write(version)
        print(f"native icons synced (version {version})")
    except Exception as e:
        print(f"native icons sync failed: {e}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)


def merge_catalog(remote_apps, native_entries):
    """Merge generated entries under the curated list.

    Curated apps.json entries win over generated ones sharing the same
    (lowercased) package_name, falling back to folder_name.
    """
    seen = set()
    for app in remote_apps:
        key = (app.get("package_name") or app.get("folder_name") or "").lower()
        if key:
            seen.add(key)
    merged = list(remote_apps)
    for entry in native_entries:
        key = (entry.get("package_name") or entry.get("folder_name") or "").lower()
        if key and key not in seen:
            seen.add(key)
            merged.append(entry)
    return merged
