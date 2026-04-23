# SPDX-License-Identifier: GPL-3.0-or-later
"""User settings persistence.

Handles loading, saving, and accessing user preferences stored in
``~/.appstore/settings.json``.
"""

import json
import os

from termux_appstore.constants import DEFAULT_SETTINGS, SETTINGS_FILE


class Settings:
    """Read/write user settings with defaults for missing keys."""

    def __init__(self):
        self._data = {}
        self.load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self):
        """Load settings from disk, filling in defaults for missing keys."""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r") as f:
                    self._data = json.load(f)
                # Back-fill any keys that were added in newer versions
                changed = False
                for key, default in DEFAULT_SETTINGS.items():
                    if key not in self._data:
                        self._data[key] = default
                        changed = True
                if changed:
                    self.save()
            else:
                self._data = dict(DEFAULT_SETTINGS)
                self.save()
                print("Created default settings")
        except Exception as e:
            print(f"Error loading settings: {e}")
            self._data = dict(DEFAULT_SETTINGS)

    def save(self):
        """Persist current settings to disk."""
        try:
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key, default=None):
        """Return a setting value, falling back to *default*."""
        return self._data.get(key, default)

    def set(self, key, value):
        """Update a single setting and save immediately."""
        self._data[key] = value
        self.save()
