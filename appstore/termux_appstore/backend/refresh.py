# SPDX-License-Identifier: GPL-3.0-or-later
"""Background data refresh logic.

Downloads fresh ``apps.json`` and logos, resolves package versions,
detects installed packages, and computes pending updates — all without
any GTK imports.  The caller (window) is responsible for scheduling
this on a background thread and wiring up UI callbacks.
"""

import json
import os
import shutil
import subprocess
from datetime import datetime

from termux_appstore.backend.app_data import read_termux_desktop_config
from termux_appstore.backend.distro import (
    DistroConfig,
    check_distro_app_installed_by_path,
    check_distro_package_installed,
    check_native_package_installed,
)
from termux_appstore.constants import (
    APPSTORE_DIR,
    APPSTORE_JSON,
    APPSTORE_LOGO_DIR,
    APPSTORE_OLD_JSON_DIR,
    ARCH_COMPATIBILITY,
    GITHUB_APPS_JSON,
    GITHUB_LOGOS_ZIP,
    LAST_VERSION_CHECK_FILE,
    TERMUX_TMP,
)
from termux_appstore.utils import get_current_arch

# ---------------------------------------------------------------------------
# Logo handling
# ---------------------------------------------------------------------------


def download_and_extract_logos():
    """Download and extract the logos zip archive.

    Tries aria2c → wget → curl in order.

    Returns:
        bool: ``True`` on success (or when an existing logo directory
        can be reused after a download failure).
    """
    try:
        os.makedirs(TERMUX_TMP, exist_ok=True)
        logos_zip = os.path.join(TERMUX_TMP, "logos.zip")

        print("Downloading logos archive...")
        download_success = False

        # Try aria2c first
        for tool, cmd in [
            (
                "aria2c",
                f"aria2c -x 16 -s 16 '{GITHUB_LOGOS_ZIP}' -d '{TERMUX_TMP}' -o 'logos.zip'",
            ),
            ("wget", f"wget '{GITHUB_LOGOS_ZIP}' -O '{logos_zip}'"),
            ("curl", f"curl -L '{GITHUB_LOGOS_ZIP}' -o '{logos_zip}'"),
        ]:
            try:
                print(f"Trying {tool}...")
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    download_success = True
                    print(f"Download with {tool} successful")
                    break
                else:
                    print(f"{tool} failed: {result.stderr}")
            except Exception as e:
                print(f"Error using {tool}: {e}")

        if not download_success:
            print("All download methods failed")
            if os.path.exists(APPSTORE_LOGO_DIR) and os.listdir(APPSTORE_LOGO_DIR):
                print("Using existing logo directory since download failed")
                return True
            return False

        # Extract
        os.makedirs(APPSTORE_LOGO_DIR, exist_ok=True)
        print("Extracting logos...")
        try:
            command = f"unzip -o '{logos_zip}' -d '{APPSTORE_LOGO_DIR}'"
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if os.path.exists(logos_zip):
                os.remove(logos_zip)

            if (
                result.returncode != 0
                and os.path.exists(APPSTORE_LOGO_DIR)
                and os.listdir(APPSTORE_LOGO_DIR)
            ):
                print("Using existing logo directory since extraction failed")
                return True

            return result.returncode == 0
        except Exception as e:
            print(f"Error extracting logos: {e}")
            if os.path.exists(APPSTORE_LOGO_DIR) and os.listdir(APPSTORE_LOGO_DIR):
                print("Using existing logo directory since extraction failed")
                return True
            return False

    except Exception as e:
        print(f"Error handling logos: {e}")
        if os.path.exists(APPSTORE_LOGO_DIR) and os.listdir(APPSTORE_LOGO_DIR):
            print("Using existing logo directory since an error occurred")
            return True
        return False


# ---------------------------------------------------------------------------
# Data migration
# ---------------------------------------------------------------------------


def migrate_old_data():
    """Migrate data from the old ``~/.termux_appstore`` directory.

    Copies known data files to the new ``~/.appstore`` directory and
    removes the old directory afterwards.
    """
    from termux_appstore.constants import (
        INSTALLED_APPS_FILE,
        LAST_VERSION_CHECK_FILE,
        SETTINGS_FILE,
        UPDATES_TRACKING_FILE,
    )

    try:
        old_dir = os.path.expanduser("~/.termux_appstore")
        if not os.path.exists(old_dir):
            print("No old data directory found, nothing to migrate.")
            return

        print(f"Found old data directory: {old_dir}, migrating data...")

        migrations = [
            ("installed_apps.json", INSTALLED_APPS_FILE),
            ("updates.json", UPDATES_TRACKING_FILE),
            ("last_version_check", LAST_VERSION_CHECK_FILE),
            ("settings.json", SETTINGS_FILE),
        ]

        for filename, dest in migrations:
            old_path = os.path.join(old_dir, filename)
            if os.path.exists(old_path):
                print(f"Migrating {filename} from {old_path} to {dest}")
                shutil.copy2(old_path, dest)

        print("Migration completed successfully.")
        try:
            shutil.rmtree(old_dir)
            print(f"Removed old data directory: {old_dir}")
        except Exception as rm_error:
            print(f"Warning: Could not remove old directory: {rm_error}")
            print("You may want to manually remove it later.")

    except Exception as e:
        print(f"Error during data migration: {e}")
        import traceback

        traceback.print_exc()


# ---------------------------------------------------------------------------
# Refresh interval check
# ---------------------------------------------------------------------------


def should_auto_refresh():
    """Determine whether an automatic refresh is needed.

    Returns ``True`` when the last version check was more than 24 hours
    ago, or when no previous check is recorded.
    """
    refresh_interval = 24 * 60 * 60  # 24 hours

    if not os.path.exists(LAST_VERSION_CHECK_FILE):
        print("No last check time found, performing initial auto-refresh")
        return True

    try:
        with open(LAST_VERSION_CHECK_FILE, "r") as f:
            last_check = float(f.read().strip())

        elapsed = datetime.now().timestamp() - last_check
        if elapsed < refresh_interval:
            print(f"Last check was {elapsed:.0f}s ago, skipping auto-refresh")
            return False
        else:
            print(f"Last check was {elapsed:.0f}s ago, performing auto-refresh")
            return True
    except Exception as e:
        print(f"Error reading last check time: {e}, performing auto-refresh")
        return True


def record_refresh_timestamp():
    """Write the current timestamp to the last-version-check file."""
    try:
        os.makedirs(os.path.dirname(LAST_VERSION_CHECK_FILE), exist_ok=True)
        with open(LAST_VERSION_CHECK_FILE, "w") as f:
            f.write(str(datetime.now().timestamp()))
    except Exception as e:
        print(f"Error writing refresh timestamp: {e}")


# ---------------------------------------------------------------------------
# Main refresh pipeline  (runs on a background thread)
# ---------------------------------------------------------------------------


def refresh_data(installed_apps_manager, update_tracker, on_error=None):
    """Run the full data refresh pipeline.

    This is the pure-data counterpart of the original
    ``refresh_data_background`` method.  It should be called from a
    background thread.

    Args:
        installed_apps_manager: An :class:`~termux_appstore.backend.installed_apps.InstalledApps` instance.
        update_tracker: An :class:`~termux_appstore.backend.updates.UpdateTracker` instance.
        on_error: Optional callback ``(error_message: str) -> None``.

    Returns:
        bool: ``True`` on success.
    """
    try:
        print("\nStarting refresh process...")

        existing_updates = update_tracker.pending.copy()
        print(f"Preserving existing updates: {existing_updates}")

        system_arch = get_current_arch()
        compatible_archs = ARCH_COMPATIBILITY.get(system_arch, [system_arch])

        # 1. Ensure old_json directory exists
        os.makedirs(APPSTORE_OLD_JSON_DIR, exist_ok=True)
        old_json_path = os.path.join(APPSTORE_OLD_JSON_DIR, "apps.json")

        # 2. Back up current apps.json
        if os.path.exists(APPSTORE_JSON):
            print("Backing up current apps.json...")
            shutil.copy2(APPSTORE_JSON, old_json_path)
            os.remove(APPSTORE_JSON)

        # 3. Download new apps.json
        print("Downloading new apps.json...")
        command = (
            f"aria2c -x 16 -s 16 {GITHUB_APPS_JSON} -d {APPSTORE_DIR} -o apps.json"
        )
        result = os.system(command)
        if result != 0:
            print("Error downloading apps.json")
            if on_error:
                on_error("Failed to download apps.json")
            return False

        # 4. Handle logos
        if os.path.exists(APPSTORE_LOGO_DIR):
            print("Removing existing logos...")
            shutil.rmtree(APPSTORE_LOGO_DIR)

        print("Downloading and extracting new logos...")
        if not download_and_extract_logos():
            print("Error handling logos")
            if on_error:
                on_error("Failed to update logos")
            return False

        # 5. Filter apps by architecture
        print("Filtering apps based on architecture...")
        with open(APPSTORE_JSON, "r") as f:
            all_apps = json.load(f)

        filtered_apps = []
        for app in all_apps:
            app_arch = app.get("supported_arch", "")
            if not app_arch:
                filtered_apps.append(app)
                continue

            supported_archs = [arch.strip().lower() for arch in app_arch.split(",")]
            if any(arch in compatible_archs for arch in supported_archs):
                filtered_apps.append(app)
                print(f"Added compatible app: {app['app_name']} ({app_arch})")
            else:
                print(f"Skipped incompatible app: {app['app_name']} ({app_arch})")

        # 6. Check installed packages and resolve versions
        print("Checking installed packages and versions...")
        distro_enabled, selected_distro, _ = read_termux_desktop_config()
        distro_config = DistroConfig()

        installed_apps = set(installed_apps_manager.apps)

        _check_native_packages(filtered_apps, installed_apps)

        if distro_enabled and selected_distro:
            _check_distro_packages(
                filtered_apps, installed_apps, selected_distro, distro_config
            )

        # 7. Save results
        with open(APPSTORE_JSON, "w") as f:
            json.dump(filtered_apps, f, indent=2)

        installed_apps_manager.apps = list(installed_apps)

        # 8. Restore preserved pending updates
        for app_id, version in existing_updates.items():
            if app_id in installed_apps:
                update_tracker.add(app_id, version)
        update_tracker.save()
        print(f"Restored pending updates: {update_tracker.pending}")

        # 9. Record timestamp
        record_refresh_timestamp()

        print("Refresh completed successfully!")
        return True

    except Exception as e:
        print(f"Error during refresh: {e}")
        import traceback

        traceback.print_exc()
        if on_error:
            on_error(str(e))
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_native_packages(apps, installed_apps):
    """Resolve versions and detect installed native packages."""
    for app in apps:
        if app["app_type"] != "native":
            continue

        package_name = app.get("package_name") or app.get("run_cmd")
        if not package_name:
            continue

        if check_native_package_installed(package_name):
            print(f"Found installed native package: {package_name}")
            installed_apps.add(app["folder_name"])

        if app.get("version") == "termux_local_version":
            cmd = (
                "source /data/data/com.termux/files/usr/bin/termux-setup-package-manager && "
                'if [[ "$TERMUX_APP_PACKAGE_MANAGER" == "apt" ]]; then '
                f"apt-cache policy {package_name} | grep 'Candidate:' | awk '{{print $2}}'; "
                'elif [[ "$TERMUX_APP_PACKAGE_MANAGER" == "pacman" ]]; then '
                f"pacman -Si {package_name} 2>/dev/null | grep 'Version' | awk '{{print $3}}'; fi"
            )
            try:
                result = subprocess.run(
                    ["bash", "-c", cmd],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    app["version"] = result.stdout.strip()
                    print(f"Updated version for {app['app_name']}: {app['version']}")
            except Exception as e:
                print(f"Error getting version for {app['app_name']}: {e}")


def _check_distro_packages(apps, installed_apps, selected_distro, distro_config):
    """Resolve versions and detect installed distro packages."""
    # Verify distro is accessible
    test_cmd = f"{distro_config.get_command(selected_distro)} 'echo test'"
    try:
        test_result = subprocess.run(
            ["bash", "-c", test_cmd],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if test_result.returncode != 0:
            print(f"Error: distro test failed for {selected_distro}")
            print(f"Stderr: {test_result.stderr}")
            return
    except Exception as e:
        print(f"Error testing distro: {e}")
        return

    print(f"Checking installed packages for distro: {selected_distro}")

    for app in apps:
        if app["app_type"] != "distro":
            continue

        supported_distro = app.get("supported_distro")
        if supported_distro and supported_distro != "all":
            supported_distros = [d.strip().lower() for d in supported_distro.split(",")]
            if selected_distro not in supported_distros:
                print(
                    f"Skipping {app['app_name']}: not compatible with {selected_distro}"
                )
                continue

        package_name = app.get(f"{selected_distro}_package_name") or app.get(
            "package_name"
        )
        if not package_name:
            run_cmd = app.get(f"{selected_distro}_run_cmd") or app.get("run_cmd")
            package_name = run_cmd.split()[0] if run_cmd else None

        if not package_name:
            print(f"Skipping {app['app_name']}: no package name or run command found")
            continue

        if check_distro_package_installed(package_name, selected_distro, distro_config):
            print(f"Found installed distro package: {package_name}")
            installed_apps.add(app["folder_name"])
        elif app.get("run_cmd"):
            run_cmd = app.get(f"{selected_distro}_run_cmd") or app.get("run_cmd")
            if check_distro_app_installed_by_path(run_cmd, selected_distro):
                print(f"Found installed distro app by path: {run_cmd}")
                installed_apps.add(app["folder_name"])

        # Resolve version
        if app.get("version") == "distro_local_version":
            _resolve_distro_version(app, package_name, selected_distro, distro_config)


def _resolve_distro_version(app, package_name, selected_distro, distro_config):
    """Attempt to fetch the candidate version of a distro package."""
    base_cmd = distro_config.get_command(selected_distro)
    version_cmd = None

    if selected_distro in ("ubuntu", "debian"):
        inner = f"apt-cache policy {package_name} | grep Candidate: | awk '{{print \\$2}}' | tr -d '\\n'"
        version_cmd = f'{base_cmd} "{inner}"'
    elif selected_distro == "fedora":
        inner = f"dnf info {package_name} 2>/dev/null | awk -F': ' '/^Version/ {{print \\$2}}' | tr -d '\\n'"
        version_cmd = f'{base_cmd} "{inner}"'
    elif selected_distro == "archlinux":
        inner = f"pacman -Si {package_name} 2>/dev/null | grep Version | awk '{{print \\$3}}' | tr -d '\\n'"
        version_cmd = f'{base_cmd} "{inner}"'

    if not version_cmd:
        print(f"Skipping {app['app_name']}: unsupported distro {selected_distro}")
        return

    try:
        result = subprocess.run(
            ["bash", "-c", version_cmd],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            app["version"] = result.stdout.strip()
            print(f"Updated version for distro app {app['app_name']}: {app['version']}")
        else:
            print(f"Failed to get version for {app['app_name']}")
            if result.stderr:
                print(f"Error: {result.stderr}")
    except Exception as e:
        print(f"Error getting version for distro app {app['app_name']}: {e}")
