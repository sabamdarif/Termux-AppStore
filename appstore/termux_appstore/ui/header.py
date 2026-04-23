# SPDX-License-Identifier: GPL-3.0-or-later
"""Header bar and tab button widgets.

Creates the ``Gtk.HeaderBar`` with Explore / Installed / Updates tabs,
a search toggle button, and a hamburger menu.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # type: ignore # noqa: E402


def create_tab_button(label_text, icon_name):
    """Create a styled tab button with icon and label.

    Args:
        label_text: Button label.
        icon_name: GTK icon name.

    Returns:
        Gtk.Button
    """
    button = Gtk.Button()
    button.set_relief(Gtk.ReliefStyle.NONE)
    button.get_style_context().add_class("header-tab-button")
    button.set_size_request(120, 36)

    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
    label = Gtk.Label(label=label_text)
    hbox.pack_start(icon, False, False, 0)
    hbox.pack_start(label, False, False, 0)
    button.add(hbox)

    return button


def build_header_bar(on_section_clicked, on_menu_clicked, on_search_toggled):
    """Build and return the full header bar.

    Args:
        on_section_clicked: Callback ``(button, section_name) -> None``.
        on_menu_clicked: Callback ``(button) -> None``.
        on_search_toggled: Callback ``(button) -> None``.

    Returns:
        dict: ``{"header", "explore_button", "installed_button",
        "updates_button", "search_button", "tabs_box"}``
    """
    header = Gtk.HeaderBar()
    header.set_show_close_button(True)
    header.props.title = "Termux AppStore"

    # Tab buttons
    tabs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
    tabs_box.get_style_context().add_class("header-tabs-box")
    header.set_custom_title(tabs_box)

    explore_btn = create_tab_button("Explore", "system-search-symbolic")
    installed_btn = create_tab_button("Installed", "system-software-install-symbolic")
    updates_btn = create_tab_button("Updates", "software-update-available-symbolic")

    explore_btn.connect("clicked", on_section_clicked, "explore")
    installed_btn.connect("clicked", on_section_clicked, "installed")
    updates_btn.connect("clicked", on_section_clicked, "updates")

    # Mark explore as initially active
    explore_btn.get_style_context().add_class("active")
    explore_btn.get_style_context().add_class("selected")

    tabs_box.pack_start(explore_btn, False, False, 0)
    tabs_box.pack_start(installed_btn, False, False, 0)
    tabs_box.pack_start(updates_btn, False, False, 0)

    # Menu button (hamburger)
    menu_button = Gtk.Button()
    menu_button.set_image(
        Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON)
    )
    menu_button.get_style_context().add_class("menu-button")
    menu_button.connect("clicked", on_menu_clicked)
    header.pack_end(menu_button)

    # Search toggle button
    search_button = Gtk.Button()
    search_button.set_image(
        Gtk.Image.new_from_icon_name("system-search-symbolic", Gtk.IconSize.BUTTON)
    )
    search_button.get_style_context().add_class("menu-button")
    search_button.set_tooltip_text("Show Search")
    search_button.connect("clicked", on_search_toggled)
    header.pack_end(search_button)

    return {
        "header": header,
        "explore_button": explore_btn,
        "installed_button": installed_btn,
        "updates_button": updates_btn,
        "search_button": search_button,
        "tabs_box": tabs_box,
    }


def build_menu_popover(button, on_about, on_repos, on_settings, on_quit):
    """Build and show the hamburger menu popover.

    Args:
        button: The menu button to anchor the popover on.
        on_about: Callback for About.
        on_repos: Callback for Manage Repos.
        on_settings: Callback for Settings.
        on_quit: Callback for Quit.
    """
    popover = Gtk.Popover(relative_to=button)
    popover.set_position(Gtk.PositionType.BOTTOM)

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.set_margin_top(6)
    box.set_margin_bottom(6)
    box.set_margin_start(6)
    box.set_margin_end(6)
    box.set_spacing(2)

    about_button = Gtk.ModelButton(label="About")
    about_button.connect("clicked", on_about)
    box.pack_start(about_button, False, False, 0)

    repos_button = Gtk.ModelButton(label="Manage Repos")
    repos_button.connect("clicked", on_repos)
    box.pack_start(repos_button, False, False, 0)

    separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
    box.pack_start(separator, False, False, 6)

    settings_button = Gtk.ModelButton(label="Settings")
    settings_button.connect("clicked", on_settings)
    box.pack_start(settings_button, False, False, 0)

    separator2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
    box.pack_start(separator2, False, False, 6)

    quit_button = Gtk.ModelButton(label="Quit")
    quit_button.connect("clicked", on_quit)
    box.pack_start(quit_button, False, False, 0)

    box.show_all()
    popover.add(box)
    popover.popup()
    return popover
