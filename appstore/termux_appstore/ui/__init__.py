# SPDX-License-Identifier: GPL-3.0-or-later
"""UI widgets — header, sidebar, app card, search, and dialogs.

Usage::

    from termux_appstore.ui import (
        build_header_bar,
        build_menu_popover,
        build_sidebar,
        build_app_card,
        SearchBar,
        show_about_dialog,
        show_settings_dialog,
        show_repos_dialog,
    )
"""

from termux_appstore.ui.app_card import build_app_card
from termux_appstore.ui.dialogs import (
    show_about_dialog,
    show_repos_dialog,
    show_settings_dialog,
)
from termux_appstore.ui.header import build_header_bar, build_menu_popover
from termux_appstore.ui.search import SearchBar
from termux_appstore.ui.sidebar import build_sidebar

__all__ = [
    "build_header_bar",
    "build_menu_popover",
    "build_sidebar",
    "build_app_card",
    "SearchBar",
    "show_about_dialog",
    "show_settings_dialog",
    "show_repos_dialog",
]
