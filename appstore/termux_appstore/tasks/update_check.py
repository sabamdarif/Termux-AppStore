# SPDX-License-Identifier: GPL-3.0-or-later
"""System-update pipeline — runs on a background thread.

Downloads fresh ``apps.json``, resolves native and distro package
versions, compares against the previous snapshot, updates logos, and
reports new pending updates.  No GTK imports — the caller supplies
simple callbacks for progress and completion.
"""

import json
import os
import shutil
import subprocess
from datetime import datetime

from termux_appstore.backend.app_data import load_app_metadata
from termux_appstore.backend.refresh import (
    _check_distro_packages,
    _check_native_packages,
)
from termux_appstore.constants import (
    APPSTORE_DIR,
    APPSTORE_JSON,
    APPSTORE_LOGO_DIR,
    APPSTORE_OLD_JSON_DIR,
    GITHUB_APPS_JSON,
    GITHUB_LOGOS_ZIP,
    LAST_VERSION_CHECK_FILE,
    TERMUX_PREFIX,
)


def run_update_pipeline(
    installed_apps,
    update_tracker,
    distro_config=None,
    on_progress=None,
    on_error=None,
):
    """Execute the full update-check pipeline.

    This function is meant to be called from a **background thread**.
    It never touches GTK widgets directly — instead it invokes the
    supplied callbacks so the caller can schedule UI updates.

    Args:
        installed_apps: ``set`` (or list) of currently installed folder
            names.
        update_tracker: An
            :class:`~termux_appstore.backend.updates.UpdateTracker`
            instance.
        distro_config: Optional
            :class:`~termux_appstore.backend.distro.DistroConfig`.
            Pass ``None`` when distro support is disabled.
        on_progress: Optional ``(progress_int, label_str) -> None``
            callback.  Called at each pipeline stage.
        on_error: Optional ``(error_message_str) -> None`` callback.

    Returns:
        A ``dict`` with keys:

        * ``apps_data`` – freshly loaded app list
        * ``categories`` – category list
        * ``new_updates`` – ``{folder_name: version}`` of newly
          detected updates
        * ``pending_updates`` – full pending-update mapping after
          merging

        …or ``None`` when the pipeline fails.
    """

    def _progress(pct, label=""):
        if on_progress is not None:
            on_progress(pct, label)

    try:
        # Step 1: Update native repository (0-20%)
        _progress(0)
        _progress(10, "Updating repository...")
        cmd = (
            f"source {TERMUX_PREFIX}/bin/termux-setup-package-manager && "
            'if [[ "$TERMUX_APP_PACKAGE_MANAGER" == "apt" ]]; then '
            "apt update -y 2>/dev/null; "
            'elif [[ "$TERMUX_APP_PACKAGE_MANAGER" == "pacman" ]]; then '
            "pacman -Sy --noconfirm 2>/dev/null; fi"
        )
        subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True, timeout=60,
        )

        # Step 1b: Update distro repos (20-25%)
        _progress(20, "Checking distro repositories...")
        distro_available = False
        if distro_config is not None and distro_config.distro_enabled:
            distro = distro_config.selected_distro
            base_cmd = distro_config.get_command(distro)

            # Test distro connectivity first (like gtk_app_store.py)
            test_cmd = f"{base_cmd} 'echo test'"
            try:
                test_result = subprocess.run(
                    ["bash", "-c", test_cmd],
                    capture_output=True, text=True, timeout=10,
                )
                if test_result.returncode == 0:
                    distro_available = True
                    print(f"Distro test successful for {distro}")
                    _progress(25, f"Updating {distro} repositories...")

                    distro_cmd = _distro_update_cmd(distro, base_cmd)
                    if distro_cmd:
                        subprocess.run(
                            ["bash", "-c", distro_cmd],
                            capture_output=True, text=True, timeout=120,
                        )
                else:
                    print(
                        f"Distro test failed for {distro}: {test_result.stderr}"
                    )
            except Exception as e:
                print(f"Error testing distro: {e}")

        # Step 2: Download new app data (35%)
        _progress(35, "Downloading updates...")
        old_json_path = os.path.join(APPSTORE_OLD_JSON_DIR, "apps.json")
        old_apps_data = []
        if os.path.exists(old_json_path):
            with open(old_json_path, "r") as f:
                old_apps_data = json.load(f)

        # Backup current → old
        if os.path.exists(APPSTORE_JSON):
            os.makedirs(APPSTORE_OLD_JSON_DIR, exist_ok=True)
            shutil.copy2(APPSTORE_JSON, old_json_path)
            os.remove(APPSTORE_JSON)

        dl_cmd = (
            f"aria2c -x 16 -s 16 '{GITHUB_APPS_JSON}' "
            f"-d '{APPSTORE_DIR}' -o 'apps.json'"
        )
        subprocess.run(
            dl_cmd, shell=True, capture_output=True, text=True, timeout=60,
        )

        if not os.path.exists(APPSTORE_JSON):
            print("Failed to download new apps.json")
            if on_error:
                on_error("Failed to download new apps.json")
            return None

        with open(APPSTORE_JSON, "r") as f:
            new_apps_data = json.load(f)

        # Step 3: Resolve versions
        _progress(50, "Checking versions...")
        installed_set = set(installed_apps)
        _check_native_packages(new_apps_data, installed_set)

        if distro_available:
            _progress(60, "Checking distro versions...")
            _check_distro_packages(
                new_apps_data,
                installed_set,
                distro_config.selected_distro,
                distro_config,
            )

        # Save resolved versions
        with open(APPSTORE_JSON, "w") as f:
            json.dump(new_apps_data, f, indent=2)

        # Step 4: Compare versions for installed apps
        _progress(70, "Comparing versions...")
        new_updates = _compare_versions(
            new_apps_data, old_apps_data, installed_apps,
        )

        # Merge into tracker
        for folder, ver in new_updates.items():
            update_tracker.add(folder, ver)
        update_tracker.save()

        # Step 5: Update logos
        _progress(80, "Updating app logos...")
        _update_logos()

        # Step 6: Save last check timestamp
        _progress(90, "Finishing up...")
        os.makedirs(os.path.dirname(LAST_VERSION_CHECK_FILE), exist_ok=True)
        with open(LAST_VERSION_CHECK_FILE, "w") as f:
            f.write(str(datetime.now().timestamp()))

        # Step 7: Reload data
        _progress(100, "Check for Updates")
        apps_data, categories = load_app_metadata()

        print(f"Update check complete — {len(new_updates)} updates found")
        return {
            "apps_data": apps_data,
            "categories": categories,
            "new_updates": new_updates,
            "pending_updates": update_tracker.pending,
        }

    except Exception as e:
        print(f"Update check failed: {e}")
        import traceback
        traceback.print_exc()
        if on_error:
            on_error(f"Update check failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _distro_update_cmd(distro, base_cmd):
    """Return the repo-update command for *distro*, or ``None``."""
    if distro in ("ubuntu", "debian"):
        return f"{base_cmd} 'apt update -y'"
    if distro == "fedora":
        return f"{base_cmd} 'dnf check-update -y || true'"
    if distro == "archlinux":
        return f"{base_cmd} 'pacman -Sy --noconfirm'"
    return None


def _compare_versions(new_apps_data, old_apps_data, installed_apps):
    """Return ``{folder_name: new_version}`` for apps with changed versions."""
    skip = {
        "termux_local_version",
        "distro_local_version",
        "Unavailable",
        None,
    }
    new_updates = {}
    for new_app in new_apps_data:
        folder = new_app["folder_name"]
        if folder not in installed_apps:
            continue
        new_ver = new_app.get("version")
        if new_ver in skip:
            continue

        old_app = next(
            (a for a in old_apps_data if a["folder_name"] == folder), None,
        )
        if old_app:
            old_ver = old_app.get("version")
            if old_ver in skip:
                continue
            if old_ver != new_ver:
                new_updates[folder] = new_ver
                print(
                    f"Update found: {new_app['app_name']} {old_ver} → {new_ver}"
                )
    return new_updates


def _update_logos():
    """Download and extract fresh logo assets."""
    if os.path.exists(APPSTORE_LOGO_DIR):
        shutil.rmtree(APPSTORE_LOGO_DIR)
    logo_cmd = (
        f"aria2c -x 16 -s 16 '{GITHUB_LOGOS_ZIP}' "
        f"-d '{APPSTORE_DIR}' -o 'logos.zip' && "
        f"unzip -o '{os.path.join(APPSTORE_DIR, 'logos.zip')}' "
        f"-d '{APPSTORE_LOGO_DIR}' && "
        f"rm -f '{os.path.join(APPSTORE_DIR, 'logos.zip')}'"
    )
    subprocess.run(
        logo_cmd, shell=True, capture_output=True, text=True, timeout=120,
    )
