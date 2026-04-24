# SPDX-License-Identifier: GPL-3.0-or-later
"""Terminal emulator widget for GTK TextViews.

Wraps a ``Gtk.TextView`` with terminal-like behaviour: ANSI color
rendering, carriage-return animation handling, warning filtering,
scrolling, and save-to-file support.
"""

import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # type: ignore # noqa: E402

from termux_appstore.constants import TERMINAL_WARNING_FILTERS
from termux_appstore.terminal.ansi_parser import AnsiColorParser


class TerminalEmulator:
    """Emulates a terminal in a GTK TextView."""

    def __init__(self, text_view):
        self.text_view = text_view
        self.buffer = text_view.get_buffer()
        self.ansi_parser = AnsiColorParser()
        self.last_line_was_animation = False
        self.line_buffer = ""  # Buffer to accumulate partial lines

        # Ensure monospace font for terminal-like appearance
        self.text_view.set_monospace(True)

        # Set initial terminal colors (will be overridden by CSS)
        self.text_view.override_background_color(
            Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 1)
        )
        self.text_view.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(1, 1, 1, 1))

        # Add terminal view style class
        self.text_view.get_style_context().add_class("terminal-view")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append_text(self, text, with_ansi=True):
        """Append text to the terminal view."""
        if not text:
            return

        # Convert CR+LF to just LF
        text = text.replace("\r\n", "\n")

        # Filter warning messages
        text = self._filter_warnings(text)
        if not text:
            return

        # Special handling for carriage returns
        if "\r" in text:
            self._handle_carriage_returns(text, with_ansi)
        else:
            self._handle_normal_text(text, with_ansi)

    def clear(self):
        """Clear the terminal view."""
        self.buffer.delete(self.buffer.get_start_iter(), self.buffer.get_end_iter())
        self.last_line_was_animation = False
        self.line_buffer = ""

    def get_text(self):
        """Get the terminal contents."""
        start_iter, end_iter = self.buffer.get_bounds()
        return self.buffer.get_text(start_iter, end_iter, False)

    def save_terminal_output(self, parent_window=None, app_name=None):
        """Save terminal contents to a file.

        Args:
            parent_window: The parent window for the file dialog.
            app_name: Optional app name for the default filename.

        Returns:
            bool: ``True`` on success.
        """
        text = self.get_text()

        file_dialog = Gtk.FileChooserDialog(
            title="Save Terminal Output",
            parent=parent_window,
            action=Gtk.FileChooserAction.SAVE,
        )
        file_dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE,
            Gtk.ResponseType.OK,
        )

        home_dir = os.path.expanduser("~")
        file_dialog.set_current_folder(home_dir)
        default_filename = (
            f"{app_name.lower().replace(' ', '_')}_output.log"
            if app_name
            else "terminal_output.log"
        )
        file_dialog.set_current_name(default_filename)

        # Add file filters
        text_filter = Gtk.FileFilter()
        text_filter.set_name("Text files")
        text_filter.add_mime_type("text/plain")
        text_filter.add_pattern("*.txt")
        text_filter.add_pattern("*.log")
        file_dialog.add_filter(text_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("All files")
        all_filter.add_pattern("*")
        file_dialog.add_filter(all_filter)

        response = file_dialog.run()
        result = False

        if response == Gtk.ResponseType.OK:
            filename = file_dialog.get_filename()
            try:
                with open(filename, "w") as f:
                    f.write(self.ansi_parser.strip_ansi(text))
                self.append_text(f"\nOutput saved to {filename}\n")
                result = True
            except Exception as e:
                self.append_text(f"\nError saving output: {e}\n")
                result = False

        file_dialog.destroy()
        return result

    # ------------------------------------------------------------------
    # Internal — warning filtering
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_warnings(text):
        """Remove known warning lines from *text*."""
        if "\n" in text:
            filtered = [
                line
                for line in text.splitlines(True)
                if not any(w in line for w in TERMINAL_WARNING_FILTERS)
            ]
            return "".join(filtered) if filtered else ""
        else:
            if any(w in text for w in TERMINAL_WARNING_FILTERS):
                return ""
            return text

    # ------------------------------------------------------------------
    # Internal — carriage return / animation handling
    # ------------------------------------------------------------------

    def _handle_carriage_returns(self, text, with_ansi):
        """Handle text with carriage returns (animations)."""
        self.last_line_was_animation = True
        lines = text.split("\r")

        for i in range(len(lines) - 1):
            if not lines[i]:
                continue

            if i == 0 and self.line_buffer:
                self.line_buffer += lines[i]
                self._append_segment(self.line_buffer, with_ansi)
                self.line_buffer = ""
            elif i == 0:
                self._append_segment(lines[i], with_ansi)
            else:
                self._replace_last_line(lines[i], with_ansi)

        if lines[-1]:
            self._replace_last_line(lines[-1], with_ansi)

    def _handle_normal_text(self, text, with_ansi):
        """Handle text without carriage returns."""
        if self.line_buffer:
            text = self.line_buffer + text
            self.line_buffer = ""

        if self.last_line_was_animation and not text.startswith("\n"):
            if "\n" in text:
                self.last_line_was_animation = False

            if not text.strip().startswith("\n"):
                end_iter = self.buffer.get_end_iter()
                self.buffer.insert(end_iter, "\n")

        lines = text.split("\n")

        # Handle all complete lines
        for i in range(len(lines) - 1):
            line = lines[i]
            self._append_segment(line + "\n", with_ansi)
            self.last_line_was_animation = False

        # Handle the last line (might be incomplete)
        if lines[-1]:
            if text.endswith("\n"):
                self._append_segment(lines[-1] + "\n", with_ansi)
                self.last_line_was_animation = False
            else:
                self.line_buffer = lines[-1]
                self._append_segment(lines[-1], with_ansi)

    # ------------------------------------------------------------------
    # Internal — text insertion
    # ------------------------------------------------------------------

    def _append_segment(self, text, with_ansi=True):
        """Append a segment of text to the terminal."""
        if not text:
            return

        # Filter warnings from segments too
        text = self._filter_warnings(text)
        if not text:
            return

        # Add newline between non-animation content if needed
        if self.buffer.get_char_count() > 0 and not self.last_line_was_animation:
            end_iter = self.buffer.get_end_iter()
            start_iter = end_iter.copy()
            if start_iter.backward_char():
                last_char = self.buffer.get_text(start_iter, end_iter, False)
                if last_char != "\n" and not text.startswith("\n"):
                    self.buffer.insert(end_iter, "\n")

        if with_ansi:
            self.ansi_parser.apply_formatting(self.buffer, text)
        else:
            end_iter = self.buffer.get_end_iter()
            self.buffer.insert(end_iter, text)

        self._scroll_to_end()

    def _replace_last_line(self, text, with_ansi=True):
        """Replace the last line of the terminal (for carriage returns)."""
        end_iter = self.buffer.get_end_iter()
        line_start = self._find_line_start(end_iter)
        self.buffer.delete(line_start, end_iter)

        if with_ansi:
            self.ansi_parser.apply_formatting(self.buffer, text)
        else:
            self.buffer.insert(self.buffer.get_end_iter(), text)

        self._scroll_to_end()

    @staticmethod
    def _find_line_start(end_iter):
        """Find the start of the current line."""
        start_iter = end_iter.copy()
        start_iter.set_line_offset(0)
        return start_iter

    def _scroll_to_end(self):
        """Scroll the view to the end."""
        try:
            if not self.text_view or not isinstance(self.text_view, Gtk.TextView):
                return False
            buffer = self.text_view.get_buffer()
            if not buffer or not isinstance(buffer, Gtk.TextBuffer):
                return False
            if not self.text_view.get_mapped():
                return False
            sw = self.text_view.get_parent()
            if not sw or not isinstance(sw, Gtk.ScrolledWindow):
                return False
            vadj = sw.get_vadjustment()
            if not vadj:
                return False
            GLib.idle_add(
                lambda: vadj.set_value(vadj.get_upper() - vadj.get_page_size())
            )
            return False
        except Exception:
            return False
