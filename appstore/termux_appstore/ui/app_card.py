# SPDX-License-Identifier: GPL-3.0-or-later
"""App card widget factory.

Builds individual app cards for the app list, with logo, name,
description, version, and action buttons (Install / Open / Update /
Uninstall).
"""

import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib, Gtk  # type: ignore # noqa: E402

from termux_appstore.constants import APPSTORE_LOGO_DIR


def _format_version(version):
    """Clean a version string for display.

    Returns:
        str: Cleaned version, or ``"Unavailable"``.
    """
    if not version or not isinstance(version, str):
        return "Unavailable"

    if version in ("termux_local_version", "distro_local_version"):
        return "Unavailable"

    version = version.split(",")[0].strip()
    version = version.split()[0].strip()
    if version.startswith("v"):
        version = version[1:]
    return version or "Unavailable"


def _load_logo(app):
    """Load the app logo as a scaled ``GdkPixbuf``.

    Returns:
        Gtk.Image | None
    """
    folder = app.get("folder_name", "")
    png_path = os.path.join(APPSTORE_LOGO_DIR, folder, "logo.png")
    svg_path = os.path.join(APPSTORE_LOGO_DIR, folder, "logo.svg")

    logo_path = None
    if os.path.exists(png_path):
        logo_path = png_path
    elif os.path.exists(svg_path):
        logo_path = svg_path

    if not logo_path:
        return None

    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(logo_path, 64, 64, True)
        if pixbuf:
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            image.set_margin_end(12)
            return image
    except GLib.Error as e:
        print(f"Error loading logo for {app.get('app_name', '?')}: {e}")
    except Exception as e:
        print(f"Unexpected error loading logo for {app.get('app_name', '?')}: {e}")

    return None


def build_app_card(
    app,
    is_installed,
    has_update,
    on_install=None,
    on_uninstall=None,
    on_open=None,
    on_update=None,
):
    """Build a single app card widget.

    Args:
        app: App metadata dict from ``apps.json``.
        is_installed: Whether the app is currently installed.
        has_update: Whether a pending update exists for this app.
        on_install: Callback ``(button, app) -> None``.
        on_uninstall: Callback ``(button, app) -> None``.
        on_open: Callback ``(button, app) -> None``.
        on_update: Callback ``(button, app) -> None``.

    Returns:
        Gtk.Box: The complete app card widget.
    """
    try:
        app_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        app_card.get_style_context().add_class("app-card")

        card_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        card_box.set_margin_start(12)
        card_box.set_margin_end(12)
        card_box.set_margin_top(12)
        card_box.set_margin_bottom(12)

        # Logo
        logo_image = _load_logo(app)
        if logo_image:
            card_box.pack_start(logo_image, False, False, 0)

        # Info column
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Top row: name + source type
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        name_label = Gtk.Label()
        name_label.set_markup(f"<b>{GLib.markup_escape_text(app['app_name'])}</b>")
        name_label.set_halign(Gtk.Align.START)
        top_row.pack_start(name_label, False, False, 0)

        # Spacer
        top_row.pack_start(Gtk.Label(), True, True, 0)

        # Source type
        source_label = Gtk.Label()
        source_type = app.get("app_type", "unknown").capitalize()
        source_label.set_markup(f"Source: {GLib.markup_escape_text(source_type)}")
        source_label.get_style_context().add_class("metadata-label")
        source_label.set_size_request(120, -1)
        source_label.set_halign(Gtk.Align.CENTER)
        source_label.set_margin_end(6)
        top_row.pack_end(source_label, False, False, 0)

        info_box.pack_start(top_row, False, False, 0)

        # Description (truncated)
        desc_text = app.get("description", "")
        if len(desc_text) > 100:
            desc_text = desc_text[:100] + "..."
        desc_label = Gtk.Label(label=GLib.markup_escape_text(desc_text))
        desc_label.set_line_wrap(True)
        desc_label.set_halign(Gtk.Align.START)
        info_box.pack_start(desc_label, False, False, 0)

        # Bottom row: buttons + version
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bottom_box.set_margin_top(6)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Version label
        version_label = Gtk.Label()
        version_label.set_text(
            GLib.markup_escape_text(_format_version(app.get("version", "")))
        )
        version_label.get_style_context().add_class("metadata-label")
        version_label.set_size_request(120, -1)
        version_label.set_halign(Gtk.Align.CENTER)
        version_label.set_margin_end(6)

        # Action buttons
        if is_installed:
            if has_update and app.get("install_url") and on_update:
                update_button = Gtk.Button(label="Update")
                update_button.get_style_context().add_class("update-button")
                update_button.connect("clicked", on_update, app)
                update_button.set_size_request(120, -1)
                button_box.pack_start(update_button, False, False, 0)
            elif app.get("run_cmd") and app["run_cmd"].strip() and on_open:
                open_button = Gtk.Button(label="Open")
                open_button.get_style_context().add_class("open-button")
                open_button.connect("clicked", on_open, app)
                open_button.set_size_request(120, -1)
                button_box.pack_start(open_button, False, False, 0)

            if on_uninstall:
                uninstall_button = Gtk.Button(label="Uninstall")
                uninstall_button.get_style_context().add_class("uninstall-button")
                uninstall_button.connect("clicked", on_uninstall, app)
                uninstall_button.set_size_request(120, -1)
                button_box.pack_start(uninstall_button, False, False, 0)
        else:
            if on_install:
                install_button = Gtk.Button(label="Install")
                install_button.get_style_context().add_class("install-button")
                install_button.connect("clicked", on_install, app)
                install_button.set_size_request(120, -1)
                button_box.pack_start(install_button, False, False, 0)

        bottom_box.pack_start(button_box, False, False, 0)
        bottom_box.pack_end(version_label, False, False, 0)
        info_box.pack_start(bottom_box, False, False, 0)

        card_box.pack_start(info_box, True, True, 0)
        app_card.add(card_box)

        return app_card

    except Exception as e:
        print(f"Error building app card for {app.get('app_name', '?')}: {e}")
        import traceback

        traceback.print_exc()
        return None
