# SPDX-License-Identifier: GPL-3.0-or-later
"""Search bar widget and debounced search logic.

Builds the search entry box and provides a debounced search handler
that fires after a configurable delay.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # type: ignore # noqa: E402


class SearchBar:
    """Manages a search entry with debounce support.

    Attributes:
        box: The ``Gtk.Box`` containing the search entry.
        entry: The ``Gtk.Entry`` widget.
    """

    def __init__(self, on_search, on_activate=None, debounce_ms=300):
        """Create the search bar.

        Args:
            on_search: Callback ``(search_text: str) -> None`` fired
                after the debounce delay.
            on_activate: Optional callback ``(entry) -> None`` for
                Enter key.
            debounce_ms: Debounce delay in milliseconds.
        """
        self._on_search = on_search
        self._debounce_ms = debounce_ms
        self._timeout_id = None

        # Build widgets
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.box.set_margin_start(10)
        self.box.set_margin_end(10)
        self.box.set_margin_top(10)
        self.box.get_style_context().add_class("search-box")

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Search apps...")
        self.entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.PRIMARY, "system-search-symbolic"
        )
        self.entry.set_icon_activatable(Gtk.EntryIconPosition.PRIMARY, False)
        self.entry.get_style_context().add_class("search-entry")
        self.entry.set_size_request(-1, 40)
        self.entry.connect("changed", self._on_changed)

        if on_activate:
            self.entry.connect("activate", on_activate)

        self.box.pack_start(self.entry, True, True, 0)

        # Start hidden
        self.box.hide()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def toggle(self, search_button):
        """Toggle visibility and update the search button icon.

        Args:
            search_button: The ``Gtk.Button`` whose icon should flip.
        """
        if self.box.get_visible():
            self.box.hide()
            search_button.set_image(
                Gtk.Image.new_from_icon_name(
                    "system-search-symbolic", Gtk.IconSize.BUTTON
                )
            )
            search_button.set_tooltip_text("Show Search")
        else:
            self.box.show()
            search_button.set_image(
                Gtk.Image.new_from_icon_name(
                    "window-close-symbolic", Gtk.IconSize.BUTTON
                )
            )
            search_button.set_tooltip_text("Hide Search")
            self.entry.grab_focus()

    @property
    def text(self):
        """Return the current search text (lowercase)."""
        return self.entry.get_text().lower()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_changed(self, entry):
        """Handle entry text changes with debounce."""
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

        search_text = entry.get_text().lower()
        self._timeout_id = GLib.timeout_add(
            self._debounce_ms, self._fire_search, search_text
        )

    def _fire_search(self, search_text):
        """Execute the search callback."""
        self._timeout_id = None
        self._on_search(search_text)
        return False  # Don't repeat
