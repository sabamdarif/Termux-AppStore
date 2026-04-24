# SPDX-License-Identifier: GPL-3.0-or-later
"""ANSI escape sequence parser for GTK TextViews.

Parses SGR (Select Graphic Rendition) codes and applies corresponding
GTK text tags for colors, bold, italic, underline, etc.
"""

import re

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Pango  # type: ignore # noqa: E402


class AnsiColorParser:
    """Parse ANSI escape sequences and apply formatting to a GTK TextView."""

    # ANSI escape sequence regex
    ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[((?:\d+;)*\d+)?([A-Za-z])")

    # Basic ANSI color codes
    COLORS = {
        # Foreground colors
        "30": (0.0, 0.0, 0.0),  # Black
        "31": (0.8, 0.0, 0.0),  # Red
        "32": (0.0, 0.8, 0.0),  # Green
        "33": (0.8, 0.8, 0.0),  # Yellow
        "34": (0.0, 0.0, 0.8),  # Blue
        "35": (0.8, 0.0, 0.8),  # Magenta
        "36": (0.0, 0.8, 0.8),  # Cyan
        "37": (0.8, 0.8, 0.8),  # White
        "90": (0.5, 0.5, 0.5),  # Bright Black (Gray)
        "91": (1.0, 0.0, 0.0),  # Bright Red
        "92": (0.0, 1.0, 0.0),  # Bright Green
        "93": (1.0, 1.0, 0.0),  # Bright Yellow
        "94": (0.0, 0.0, 1.0),  # Bright Blue
        "95": (1.0, 0.0, 1.0),  # Bright Magenta
        "96": (0.0, 1.0, 1.0),  # Bright Cyan
        "97": (1.0, 1.0, 1.0),  # Bright White
        # Background colors
        "40": (0.0, 0.0, 0.0),  # Black
        "41": (0.8, 0.0, 0.0),  # Red
        "42": (0.0, 0.8, 0.0),  # Green
        "43": (0.8, 0.8, 0.0),  # Yellow
        "44": (0.0, 0.0, 0.8),  # Blue
        "45": (0.8, 0.0, 0.8),  # Magenta
        "46": (0.0, 0.8, 0.8),  # Cyan
        "47": (0.8, 0.8, 0.8),  # White
        "100": (0.5, 0.5, 0.5),  # Bright Black (Gray)
        "101": (1.0, 0.0, 0.0),  # Bright Red
        "102": (0.0, 1.0, 0.0),  # Bright Green
        "103": (1.0, 1.0, 0.0),  # Bright Yellow
        "104": (0.0, 0.0, 1.0),  # Bright Blue
        "105": (1.0, 0.0, 1.0),  # Bright Magenta
        "106": (0.0, 1.0, 1.0),  # Bright Cyan
        "107": (1.0, 1.0, 1.0),  # Bright White
    }

    # Text attributes
    ATTRIBUTES = {
        "0": {"name": "reset", "tags": []},
        "1": {"name": "bold", "tags": ["bold"]},
        "2": {"name": "dim", "tags": ["dim"]},
        "3": {"name": "italic", "tags": ["italic"]},
        "4": {"name": "underline", "tags": ["underline"]},
        "5": {"name": "blink", "tags": ["blink"]},
        "7": {"name": "reverse", "tags": ["reverse"]},
        "9": {"name": "strikethrough", "tags": ["strikethrough"]},
    }

    def __init__(self):
        # Initialize tag table for the TextView buffer
        self.active_tags = []

    def ensure_tag(self, buffer, tag_name, properties):
        """Ensure a tag exists in the buffer with given properties."""
        tag = buffer.get_tag_table().lookup(tag_name)
        if not tag:
            tag = buffer.create_tag(tag_name, **properties)
        return tag

    def apply_formatting(self, buffer, text):
        """Apply ANSI formatting to text and insert into buffer."""
        if not text:
            return

        i = 0
        last_text_pos = 0

        while i < len(text):
            match = self.ANSI_ESCAPE_PATTERN.search(text, i)

            if not match:
                # No more escape sequences, insert the rest of the text
                plain_text = text[last_text_pos:]
                if plain_text:
                    self._insert_with_active_tags(buffer, plain_text)
                break

            # Insert any text before the escape sequence
            if match.start() > last_text_pos:
                plain_text = text[last_text_pos : match.start()]
                self._insert_with_active_tags(buffer, plain_text)

            # Process the ANSI code
            codes = match.group(1)
            command = match.group(2)

            if command == "m":  # SGR (Select Graphic Rendition)
                if codes:
                    self._process_sgr_codes(buffer, codes)
                else:
                    # Reset all attributes if no codes provided
                    self.active_tags = []

            # Move past the escape sequence
            i = match.end()
            last_text_pos = i

    def _insert_with_active_tags(self, buffer, text):
        """Insert text into buffer with active tags applied."""
        if not text:
            return

        end_iter = buffer.get_end_iter()
        mark = buffer.create_mark(None, end_iter, True)

        buffer.insert(end_iter, text)

        # Get the start and end positions of the newly inserted text
        new_end_iter = buffer.get_end_iter()
        start_iter = buffer.get_iter_at_mark(mark)

        # Apply all active tags to the inserted text
        for tag_name in self.active_tags:
            tag = buffer.get_tag_table().lookup(tag_name)
            if tag:
                buffer.apply_tag(tag, start_iter, new_end_iter)

        buffer.delete_mark(mark)

    def _process_sgr_codes(self, buffer, codes_str):
        """Process SGR (Select Graphic Rendition) codes."""
        codes = codes_str.split(";")

        for code in codes:
            if not code:
                continue

            # Handle reset
            if code == "0":
                self.active_tags = []
                continue

            # Text attribute
            if code in self.ATTRIBUTES and code != "0":
                for tag_type in self.ATTRIBUTES[code]["tags"]:
                    tag_name = f"ansi_{tag_type}"

                    if tag_type == "bold":
                        self.ensure_tag(buffer, tag_name, {"weight": Pango.Weight.BOLD})
                    elif tag_type == "dim":
                        self.ensure_tag(
                            buffer, tag_name, {"weight": Pango.Weight.LIGHT}
                        )
                    elif tag_type == "italic":
                        self.ensure_tag(buffer, tag_name, {"style": Pango.Style.ITALIC})
                    elif tag_type == "underline":
                        self.ensure_tag(
                            buffer, tag_name, {"underline": Pango.Underline.SINGLE}
                        )
                    elif tag_type == "blink":
                        self.ensure_tag(buffer, tag_name, {"background": "lightgray"})
                    elif tag_type == "reverse":
                        self.ensure_tag(
                            buffer,
                            tag_name,
                            {"background": "white", "foreground": "black"},
                        )
                    elif tag_type == "strikethrough":
                        self.ensure_tag(buffer, tag_name, {"strikethrough": True})

                    if tag_name not in self.active_tags:
                        self.active_tags.append(tag_name)

            # Foreground color
            elif code.startswith("3") or code.startswith("9"):
                if code in self.COLORS:
                    r, g, b = self.COLORS[code]
                    tag_name = f"ansi_fg_{code}"
                    self.ensure_tag(
                        buffer, tag_name, {"foreground-rgba": Gdk.RGBA(r, g, b, 1.0)}
                    )

                    # Replace any existing foreground color
                    self.active_tags = [
                        tag
                        for tag in self.active_tags
                        if not tag.startswith("ansi_fg_")
                    ]
                    self.active_tags.append(tag_name)

            # Background color
            elif code.startswith("4") or code.startswith("10"):
                if code in self.COLORS:
                    r, g, b = self.COLORS[code]
                    tag_name = f"ansi_bg_{code}"
                    self.ensure_tag(
                        buffer, tag_name, {"background-rgba": Gdk.RGBA(r, g, b, 1.0)}
                    )

                    # Replace any existing background color
                    self.active_tags = [
                        tag
                        for tag in self.active_tags
                        if not tag.startswith("ansi_bg_")
                    ]
                    self.active_tags.append(tag_name)

    def strip_ansi(self, text):
        """Remove ANSI escape sequences from text."""
        return self.ANSI_ESCAPE_PATTERN.sub("", text)
