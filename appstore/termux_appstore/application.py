# SPDX-License-Identifier: GPL-3.0-or-later
"""Gtk.Application subclass for Termux AppStore.

This is the top-level application object that manages the window
lifecycle and sets up the GNOME desktop integration (icon, name).
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk  # type: ignore # noqa: E402

from termux_appstore.constants import APP_NAME


class AppStoreApplication(Gtk.Application):
    """The main Gtk.Application for Termux AppStore."""

    def __init__(self):
        Gtk.Application.__init__(
            self,
            application_id="org.sabamdarif.termux.appstore",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.window = None
        self.connect("activate", self.on_activate)

    def do_startup(self):
        """Called once when the application starts."""
        Gtk.Application.do_startup(self)

        GLib.set_application_name(APP_NAME)
        icon_theme = Gtk.IconTheme.get_default()
        try:
            icon = icon_theme.load_icon("org.gnome.Software", 128, 0)
            Gtk.Window.set_default_icon(icon)
        except Exception as e:
            print(f"Failed to set application icon: {e}")

    def on_activate(self, app):
        """Called when the application is activated (or re-focused)."""
        if self.window:
            self.window.present()
            return

        # Import here to avoid circular imports — window imports many modules
        from termux_appstore.window import AppStoreWindow

        self.window = AppStoreWindow(self)
        self.window.present()
