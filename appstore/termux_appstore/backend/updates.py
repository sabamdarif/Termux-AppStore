# SPDX-License-Identifier: GPL-3.0-or-later
"""Update tracking and version comparison.

Manages pending updates, compares versions between old and new
``apps.json`` snapshots, and persists the tracking file.
"""

import json
import os

from termux_appstore.constants import UPDATES_TRACKING_FILE


class UpdateTracker:
    """Track pending app updates."""

    def __init__(self):
        self._file = UPDATES_TRACKING_FILE
        self._pending = {}
        self.load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self):
        """Load pending updates from the tracking file."""
        try:
            if os.path.exists(self._file):
                print(f"Loading updates from {self._file}")
                with open(self._file, "r") as f:
                    self._pending = json.load(f)
                print(f"Loaded updates: {self._pending}")
            else:
                print(f"No updates file found at {self._file}")
                self._pending = {}
        except Exception as e:
            print(f"Error loading updates tracking: {e}")
            self._pending = {}

    def save(self):
        """Persist pending updates to disk."""
        try:
            os.makedirs(os.path.dirname(self._file), exist_ok=True)
            print(f"Saving updates to {self._file}")
            print(f"Updates to save: {self._pending}")
            with open(self._file, "w") as f:
                json.dump(self._pending, f, indent=2)
            print("Successfully saved updates")
        except Exception as e:
            print(f"Error saving updates tracking: {e}")
            import traceback

            traceback.print_exc()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def pending(self):
        """Return the dict of ``{folder_name: new_version}``."""
        return dict(self._pending)

    @pending.setter
    def pending(self, value):
        """Replace the pending dict and save."""
        self._pending = dict(value)
        self.save()

    def add(self, folder_name, new_version):
        """Record a pending update for *folder_name*."""
        self._pending[folder_name] = new_version

    def remove(self, folder_name):
        """Remove a pending update entry."""
        self._pending.pop(folder_name, None)

    def clear(self):
        """Remove all pending updates."""
        self._pending.clear()

    def has_updates(self):
        """Return ``True`` when there are pending updates."""
        return bool(self._pending)

    # ------------------------------------------------------------------
    # Version comparison
    # ------------------------------------------------------------------

    @staticmethod
    def compare_versions(old_data, new_data):
        """Compare versions between two ``apps.json`` snapshots.

        Args:
            old_data: List of app dicts from the old snapshot.
            new_data: List of app dicts from the new snapshot.

        Returns:
            dict: ``{folder_name: new_version}`` for apps whose version
            changed.
        """
        updates = {}
        print("\nComparing versions:")
        for new_app in new_data:
            app_name = new_app["folder_name"]
            new_version = new_app.get("version")

            old_app = next(
                (app for app in old_data if app["folder_name"] == app_name), None
            )
            if old_app:
                old_version = old_app.get("version")
                print(f"Comparing {app_name}: old={old_version}, new={new_version}")
                if new_version and old_version != new_version:
                    print(
                        f"Update found for {app_name}: {old_version} -> {new_version}"
                    )
                    updates[app_name] = new_version

        print(f"Total updates found: {len(updates)}")
        print(f"Updates: {updates}")
        return updates
