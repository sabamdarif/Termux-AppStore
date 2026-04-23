# SPDX-License-Identifier: GPL-3.0-or-later
"""Distro integration — detection, command building, and package checks.

Handles proot-distro / chroot-distro configuration and provides helpers
to check whether native or distro packages are installed.
"""

import os
import re
import shutil
import subprocess

from termux_appstore.constants import TERMUX_PREFIX

# ---------------------------------------------------------------------------
# Distro configuration
# ---------------------------------------------------------------------------


class DistroConfig:
    """Reads and caches the distro configuration."""

    def __init__(self):
        self.selected_distro = None
        self.distro_enabled = False
        self.selected_distro_type = "proot"  # "proot" or "chroot"
        self.load()

    def load(self):
        """Load distro settings from termux-desktop ``configuration.conf``.

        Reads ``distro_add_answer``, ``selected_distro``, and
        ``selected_distro_type`` directly from the termux-desktop
        configuration file.
        """
        try:
            termux_desktop_config = os.path.join(
                TERMUX_PREFIX, "etc", "termux-desktop", "configuration.conf"
            )
            if not os.path.exists(termux_desktop_config):
                print(
                    "Termux desktop config not found. "
                    "Distro support disabled."
                )
                return

            with open(termux_desktop_config, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("distro_add_answer="):
                        value = (
                            line.split("=")[1]
                            .strip()
                            .strip('"')
                            .strip("'")
                            .lower()
                        )
                        self.distro_enabled = value in ("y", "yes")
                        print(
                            f"distro_add_answer={value} -> enabled: {self.distro_enabled}"
                        )
                    elif line.startswith("selected_distro="):
                        self.selected_distro = (
                            line.split("=")[1]
                            .strip()
                            .strip('"')
                            .strip("'")
                            .lower()
                        )
                        print(f"selected_distro: {self.selected_distro}")
                    elif line.startswith("selected_distro_type="):
                        self.selected_distro_type = (
                            line.split("=")[1]
                            .strip()
                            .strip('"')
                            .strip("'")
                            .lower()
                        )
                        print(
                            f"selected_distro_type: {self.selected_distro_type}"
                        )

        except Exception as e:
            print(f"Error reading distro configuration: {e}")
            self.distro_enabled = False
            self.selected_distro = None
            self.selected_distro_type = "proot"

    def get_command(self, selected_distro=None):
        """Build the distro login command prefix.

        Args:
            selected_distro: Override the configured distro name.

        Returns:
            str: e.g. ``"proot-distro login ubuntu --shared-tmp -- /bin/bash -c"``
        """
        if selected_distro is None:
            selected_distro = self.selected_distro

        if self.selected_distro_type == "chroot":
            return f"chroot-distro login {selected_distro} --shared-tmp -- /bin/bash -c"
        else:
            return f"proot-distro login {selected_distro} --shared-tmp -- /bin/bash -c"


# ---------------------------------------------------------------------------
# Package installation checks
# ---------------------------------------------------------------------------


def check_package_installed(package_name):
    """Check if a package is installed using the system package manager.

    Works with both apt and pacman.

    Returns:
        bool: ``True`` when the package is installed.
    """
    try:
        pkg_manager = "apt"
        if shutil.which("pacman"):
            pkg_manager = "pacman"

        if pkg_manager == "apt":
            cmd = f"dpkg -s {package_name}"
            result = subprocess.run(
                cmd.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return result.returncode == 0
        elif pkg_manager == "pacman":
            cmd = f"pacman -Qi {package_name}"
            result = subprocess.run(
                cmd.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return result.returncode == 0
        return False
    except Exception:
        return False


def check_native_package_installed(package_name):
    """Check if a native Termux package is installed.

    Detects the package manager (apt/pacman) via
    ``termux-setup-package-manager`` and runs the appropriate query.

    Returns:
        bool: ``True`` when the package is installed.
    """
    try:
        cmd = (
            f"source {TERMUX_PREFIX}/bin/termux-setup-package-manager "
            "&& echo $TERMUX_APP_PACKAGE_MANAGER"
        )
        result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
        pkg_manager = result.stdout.strip()

        if pkg_manager == "apt":
            cmd = f"dpkg -l | grep -q '^ii  {package_name}'"
            if subprocess.run(["bash", "-c", cmd], capture_output=True).returncode == 0:
                return True
            cmd = f"apt list --installed 2>/dev/null | grep -q '^{package_name}/'"
            return (
                subprocess.run(["bash", "-c", cmd], capture_output=True).returncode == 0
            )

        elif pkg_manager == "pacman":
            cmd = f"pacman -Qi {package_name} 2>/dev/null"
            if subprocess.run(["bash", "-c", cmd], capture_output=True).returncode == 0:
                return True
            cmd = f"pacman -Q {package_name} 2>/dev/null"
            return (
                subprocess.run(["bash", "-c", cmd], capture_output=True).returncode == 0
            )

        return False
    except Exception as e:
        print(f"Error checking package installation status: {e}")
        return False


def check_distro_package_installed(package_name, selected_distro, distro_config):
    """Check if a package is installed inside the selected distro.

    Args:
        package_name: Package name to check.
        selected_distro: Distro name (e.g. ``"ubuntu"``).
        distro_config: A :class:`DistroConfig` instance.

    Returns:
        bool: ``True`` when the package is installed.
    """
    try:
        cmd = distro_config.get_command(selected_distro)

        if selected_distro in ("ubuntu", "debian"):
            cmd += f' \'dpkg -l | grep -q "^ii  {package_name}" || '
            cmd += f'apt list --installed 2>/dev/null | grep -q "^{package_name}/"\''
        elif selected_distro == "fedora":
            cmd += f" 'rpm -q {package_name} >/dev/null 2>&1'"
        elif selected_distro == "archlinux":
            cmd += f" 'pacman -Qi {package_name} >/dev/null 2>&1 || "
            cmd += f"pacman -Q {package_name} >/dev/null 2>&1'"

        result = subprocess.run(["bash", "-c", cmd], capture_output=True)
        return result.returncode == 0

    except Exception as e:
        print(f"Error checking distro package installation status: {e}")
        return False


def check_distro_app_installed_by_path(run_cmd, selected_distro):
    """Check if a distro app is installed by verifying executable path.

    Args:
        run_cmd: The run command from apps.json.
        selected_distro: Distro name.

    Returns:
        bool: ``True`` when the path exists (currently incomplete upstream).
    """
    if not run_cmd or not selected_distro:
        return False

    path_match = re.search(r"/[^ ]+", run_cmd)
    if not path_match:
        return False

    # NOTE: The original code had an incomplete implementation here.
    # path_match.group(0).strip() was called but the result was unused.
    return False
