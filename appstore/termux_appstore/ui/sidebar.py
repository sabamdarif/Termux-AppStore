# SPDX-License-Identifier: GPL-3.0-or-later
"""Category sidebar widget.

Builds the left panel with a scrollable list of category filter
buttons.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # type: ignore # noqa: E402


def build_sidebar(categories, on_category_clicked):
    """Build the category sidebar.

    Args:
        categories: Sorted list of category name strings.
        on_category_clicked: Callback ``(button) -> None``.

    Returns:
        dict: ``{"sidebar", "category_buttons"}``
    """
    sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    sidebar.set_size_request(200, -1)
    sidebar.set_margin_start(10)
    sidebar.set_margin_end(10)
    sidebar.set_margin_top(10)
    sidebar.set_margin_bottom(10)

    # Header label
    categories_label = Gtk.Label()
    categories_label.set_markup("<b>Categories</b>")
    categories_label.set_xalign(0)
    categories_label.set_margin_start(10)
    categories_label.set_margin_top(10)
    categories_label.set_margin_bottom(10)
    sidebar.pack_start(categories_label, False, True, 0)

    # "All Apps" button — selected by default
    all_button = Gtk.Button(label="All Apps")
    all_button.connect("clicked", on_category_clicked)
    all_button.set_size_request(180, 40)
    all_button.get_style_context().add_class("category-button")
    all_button.get_style_context().add_class("selected")
    sidebar.pack_start(all_button, False, True, 0)

    category_buttons = [all_button]

    for category in sorted(categories):
        button = Gtk.Button(label=category)
        button.connect("clicked", on_category_clicked)
        button.set_size_request(180, 40)
        button.get_style_context().add_class("category-button")
        sidebar.pack_start(button, False, True, 0)
        category_buttons.append(button)

    return {
        "sidebar": sidebar,
        "category_buttons": category_buttons,
    }
