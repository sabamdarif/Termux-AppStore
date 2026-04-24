# SPDX-License-Identifier: GPL-3.0-or-later
"""Application-wide constants for Termux AppStore.

All hardcoded paths, URLs, version strings, and configuration defaults
live here so they can be imported by any module without circular deps.
"""

import os

# ---------------------------------------------------------------------------
# Application identity
# ---------------------------------------------------------------------------
APP_ID = "org.sabamdarif.termux.appstore"
APP_NAME = "Termux AppStore"
APP_VERSION = "0.5.4.1"
APP_COMMENT = "A modern graphical package manager for Termux"
APP_COPYRIGHT = "© 2025 Termux Desktop (sabamdarif)"
APP_WEBSITE = "https://github.com/sabamdarif/termux-desktop"
APP_WEBSITE_LABEL = "Website (GITHUB)"
APP_ICON_NAME = "system-software-install"

# ---------------------------------------------------------------------------
# Termux environment paths
# ---------------------------------------------------------------------------
try:
    from termux_appstore._buildconf import PREFIX as _PREFIX
except ImportError:
    # Fallback for development runs outside meson install
    _PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")

TERMUX_PREFIX = _PREFIX
TERMUX_TMP = os.path.join(TERMUX_PREFIX, "tmp")

# ---------------------------------------------------------------------------
# App store local data paths  (all under ~/.appstore)
# ---------------------------------------------------------------------------
APPSTORE_DIR = os.path.expanduser("~/.appstore")
APPSTORE_LOGO_DIR = os.path.join(APPSTORE_DIR, "logo")
APPSTORE_JSON = os.path.join(APPSTORE_DIR, "apps.json")
APPSTORE_OLD_JSON_DIR = os.path.join(APPSTORE_DIR, "old_json")
LAST_REFRESH_FILE = os.path.join(APPSTORE_DIR, "last_refresh")
UPDATES_TRACKING_FILE = os.path.join(APPSTORE_DIR, "updates.json")
INSTALLED_APPS_FILE = os.path.join(APPSTORE_DIR, "installed_apps.json")
LAST_VERSION_CHECK_FILE = os.path.join(APPSTORE_DIR, "last_version_check")
SETTINGS_FILE = os.path.join(APPSTORE_DIR, "settings.json")

# ---------------------------------------------------------------------------
# Remote URLs
# ---------------------------------------------------------------------------
GITHUB_APPS_JSON = "https://github.com/sabamdarif/Termux-AppStore/releases/download/apps_data/apps.json"
GITHUB_LOGOS_ZIP = (
    "https://github.com/sabamdarif/Termux-AppStore/releases/download/logos/logos.zip"
)

# ---------------------------------------------------------------------------
# Architecture compatibility mapping
# ---------------------------------------------------------------------------
ARCH_COMPATIBILITY = {
    "aarch64": ["aarch64", "arm64", "arm", "all", "any"],
    "armv8l": ["arm", "armv7", "armhf", "all", "any"],
    "armv7l": ["arm", "armv7", "armhf", "all", "any"],
    "x86_64": ["x86_64", "amd64", "x86", "all", "any"],
    "i686": ["x86", "i686", "i386", "all", "any"],
}

# ---------------------------------------------------------------------------
# Default settings values
# ---------------------------------------------------------------------------
DEFAULT_SETTINGS = {
    "use_terminal_for_progress": False,
    "enable_auto_refresh": True,
    "show_command_output": False,
    "enable_fuzzy_search": False,
    "last_category": "All Apps",
}

# ---------------------------------------------------------------------------
# Termux repository definitions
# ---------------------------------------------------------------------------
TERMUX_REPOS = [
    {
        "name": "x11-repo",
        "label": "X11 Repository",
        "desc": "Package repository containing X11 programs and libraries",
    },
    {
        "name": "root-repo",
        "label": "Root Repository",
        "desc": "Package repository containing programs for rooted devices",
    },
    {
        "name": "tur-repo",
        "label": "TUR Repository",
        "desc": "A single and trusted place for all unofficial/less popular termux packages",
    },
    {
        "name": "glibc-repo",
        "label": "Glibc Repository",
        "desc": "A package repository containing glibc-based programs and libraries",
    },
]

# ---------------------------------------------------------------------------
# Terminal warning filters (messages to suppress in terminal output)
# ---------------------------------------------------------------------------
TERMINAL_WARNING_FILTERS = [
    "proot warning: can't sanitize binding",
    "WARNING: apt does not have a stable CLI interface",
]
