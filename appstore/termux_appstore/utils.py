# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared utility functions for Termux AppStore.

Pure helper functions that don't depend on GTK or any UI layer.
"""

import os
import platform
import socket
import urllib.request

from termux_appstore.constants import ARCH_COMPATIBILITY

# ---------------------------------------------------------------------------
# Architecture helpers
# ---------------------------------------------------------------------------


def get_current_arch():
    """Return the current system architecture in lowercase.

    Returns:
        str: e.g. ``"aarch64"``, ``"x86_64"``, ``"armv7l"``
    """
    return platform.machine().lower()


def is_arch_compatible(app_arch, system_arch=None):
    """Check if an app's architecture string is compatible with the system.

    Args:
        app_arch: Comma-separated architecture string from apps.json
                  (e.g. ``"aarch64,arm64"``).  ``None`` or empty means
                  the app is compatible with everything.
        system_arch: Override for the current architecture (mainly for
                     testing).  Defaults to :func:`get_current_arch`.

    Returns:
        bool: ``True`` when the app can run on this system.
    """
    if not app_arch:
        return True

    if system_arch is None:
        system_arch = get_current_arch()

    supported = [arch.strip().lower() for arch in app_arch.split(",")]
    compatible = ARCH_COMPATIBILITY.get(system_arch, [system_arch])
    return any(arch in compatible for arch in supported)


# ---------------------------------------------------------------------------
# Logo validation
# ---------------------------------------------------------------------------


def validate_logo_size(logo_path):
    """Check if a logo image is within the required size range (20–180px).

    If Pillow is not installed the check is skipped and ``True`` is
    returned.

    Args:
        logo_path: Absolute path to the image file.

    Returns:
        bool: ``True`` when the logo is valid (or cannot be checked).
    """
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return True  # skip validation when Pillow is not installed

    try:
        with Image.open(logo_path) as img:
            width, height = img.size
            if 20 <= width <= 180 and 20 <= height <= 180:
                return True
            else:
                print(
                    f"Logo for {os.path.basename(logo_path)} is not within "
                    f"the required size range (20x20 to 180x180)."
                )
                return False
    except Exception as e:
        print(f"Error validating logo size for {logo_path}: {e}")
        return False


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------


def check_internet_connection():
    """Check whether the device has an active internet connection.

    Tries multiple endpoints in order:
    1. Google DNS (8.8.8.8:53)
    2. Cloudflare DNS (1.1.1.1:53)
    3. HTTPS to google.com
    4. HTTPS to github.com (where app data is hosted)

    Returns:
        bool: ``True`` when at least one connection succeeds.
    """
    # Fast TCP checks first
    for host in ("8.8.8.8", "1.1.1.1"):
        try:
            socket.create_connection((host, 53), timeout=3)
            print(f"Internet connection check successful: Connected to {host}")
            return True
        except (socket.timeout, socket.error, OSError) as e:
            print(f"Connection to {host} failed: {e}")

    # Fall back to HTTP(S) endpoints
    for url in ("https://www.google.com", "https://github.com"):
        try:
            urllib.request.urlopen(url, timeout=3)
            print(f"Internet connection check successful: Connected to {url}")
            return True
        except Exception as e:
            print(f"Connection to {url} failed: {e}")

    print("All connection attempts failed, no internet connectivity detected")
    return False
