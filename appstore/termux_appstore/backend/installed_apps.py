# SPDX-License-Identifier: GPL-3.0-or-later
"""Installed apps tracking.

Manages the ``installed_apps.json`` file that records which apps the
user has installed through the app store.
"""

import json
import os
from pathlib import Path

from termux_appstore.constants import INSTALLED_APPS_FILE


class InstalledApps:
    """CRUD operations for the installed-apps list."""

    def __init__(self):
        self._file = Path(INSTALLED_APPS_FILE)
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._apps = []
        self.load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self):
        """Load the installed-apps list from disk."""
        try:
            if os.path.exists(self._file):
                with open(self._file) as f:
                    self._apps = json.load(f)
            else:
                self._apps = []
                self.save()
        except (FileNotFoundError, json.JSONDecodeError):
            self._apps = []
            self.save()

    def save(self):
        """Persist the installed-apps list to disk."""
        with open(self._file, "w") as f:
            json.dump(self._apps, f, indent=2)

    def update_status(self, app_name, installed):
        """Add or remove *app_name* from the installed list and save.

        Args:
            app_name: The ``folder_name`` of the app.
            installed: ``True`` to mark installed, ``False`` to remove.
        """
        if installed and app_name not in self._apps:
            self._apps.append(app_name)
        elif not installed and app_name in self._apps:
            self._apps.remove(app_name)
        self.save()

    def is_installed(self, app_name):
        """Check whether *app_name* is in the installed list."""
        return app_name in self._apps

    @property
    def apps(self):
        """Return the current list of installed app folder names."""
        return list(self._apps)

    @apps.setter
    def apps(self, value):
        """Replace the installed list and save."""
        self._apps = list(value)
        self.save()

    @property
    def file_path(self):
        """Return the path to the installed-apps JSON file."""
        return self._file
