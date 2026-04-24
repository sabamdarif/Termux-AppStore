# SPDX-License-Identifier: GPL-3.0-or-later
"""App metadata loading and filtering.

Reads ``apps.json``, filters by architecture and distro compatibility,
and exposes the resulting list plus extracted categories.
"""

import json
import os

from termux_appstore.constants import (
    APPSTORE_JSON,
    ARCH_COMPATIBILITY,
    TERMUX_PREFIX,
)
from termux_appstore.utils import get_current_arch

# ---------------------------------------------------------------------------
# Termux Desktop config reader  (shared helper, no GTK)
# ---------------------------------------------------------------------------

TERMUX_DESKTOP_CONFIG = os.path.join(
    TERMUX_PREFIX, "etc", "termux-desktop", "configuration.conf"
)


def read_termux_desktop_config():
    """Parse the Termux Desktop ``configuration.conf`` file.

    Returns:
        tuple: ``(distro_enabled: bool, selected_distro: str | None,
                  selected_distro_type: str)``
    """
    distro_enabled = False
    selected_distro = None
    selected_distro_type = "proot"

    if not os.path.exists(TERMUX_DESKTOP_CONFIG):
        print("Warning: Termux Desktop configuration file not found")
        return distro_enabled, selected_distro, selected_distro_type

    try:
        with open(TERMUX_DESKTOP_CONFIG, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue

                if line.startswith("distro_add_answer="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'").lower()
                    if value in ("y", "yes"):
                        distro_enabled = True
                    elif value in ("n", "no"):
                        distro_enabled = False
                    else:
                        print(
                            f"Warning: Unrecognized value for distro_add_answer: '{value}'"
                        )
                    print(
                        f"Found distro_add_answer: {value} -> enabled: {distro_enabled}"
                    )

                elif line.startswith("selected_distro="):
                    selected_distro = (
                        line.split("=", 1)[1].strip().strip('"').strip("'").lower()
                    )
                    print(f"Found selected_distro: {selected_distro}")

                elif line.startswith("selected_distro_type="):
                    selected_distro_type = (
                        line.split("=", 1)[1].strip().strip('"').strip("'").lower()
                    )
                    print(f"Found selected_distro_type: {selected_distro_type}")

    except Exception as e:
        print(f"Error reading Termux Desktop config: {e}")
        import traceback

        traceback.print_exc()

    return distro_enabled, selected_distro, selected_distro_type


# ---------------------------------------------------------------------------
# App metadata loading
# ---------------------------------------------------------------------------


def load_app_metadata():
    """Load and filter app metadata from ``apps.json``.

    Reads the local ``apps.json``, filters apps by system architecture
    and distro configuration, and returns the compatible app list plus
    sorted category names.

    Returns:
        tuple: ``(apps_data: list[dict], categories: list[str])``
    """
    try:
        system_arch = get_current_arch()
        compatible_archs = ARCH_COMPATIBILITY.get(system_arch, [system_arch])
        print(f"System architecture: {system_arch}")
        print(f"Compatible architectures: {compatible_archs}")

        distro_enabled, selected_distro, _ = read_termux_desktop_config()
        print(f"\nConfiguration status:")
        print(f"Distro enabled: {distro_enabled}")
        print(f"Selected distro: {selected_distro}")

        with open(APPSTORE_JSON) as f:
            all_apps = json.load(f)

        apps_data = _filter_apps(
            all_apps, compatible_archs, distro_enabled, selected_distro
        )

        categories = sorted(
            list(set(cat for app in apps_data for cat in app["categories"]))
        )

        print(
            f"Loaded {len(apps_data)} compatible apps out of {len(all_apps)} total apps"
        )
        return apps_data, categories

    except FileNotFoundError:
        print("No apps.json file found")
        return [], []
    except Exception as e:
        print(f"Error loading app metadata: {e}")
        return [], []


def _filter_apps(all_apps, compatible_archs, distro_enabled, selected_distro):
    """Filter apps by architecture and distro compatibility."""
    result = []
    for app in all_apps:
        app_arch = app.get("supported_arch", "")
        if not app_arch:
            result.append(app)
            continue

        supported_archs = [arch.strip().lower() for arch in app_arch.split(",")]

        if not any(arch in compatible_archs for arch in supported_archs):
            print(f"Skipped incompatible app: {app['app_name']} ({app_arch})")
            continue

        # Native apps pass through directly
        if app.get("app_type") != "distro":
            result.append(app)
            print(f"Added compatible app: {app['app_name']} ({app_arch})")
            continue

        # Distro apps need additional checks
        if not distro_enabled:
            print(f"Skipping distro app {app['app_name']}: distro support disabled")
            continue

        supported_distro = app.get("supported_distro")
        if supported_distro == "all":
            result.append(app)
            print(f"Added compatible app: {app['app_name']} ({app_arch})")
        elif supported_distro:
            supported_distros = [d.strip().lower() for d in supported_distro.split(",")]
            if selected_distro in supported_distros:
                result.append(app)
                print(f"Added compatible app: {app['app_name']} ({app_arch})")
            else:
                print(
                    f"Skipping incompatible distro app {app['app_name']}: "
                    f"requires one of {supported_distros}, but using {selected_distro}"
                )

    return result
