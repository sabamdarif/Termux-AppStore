# SPDX-License-Identifier: GPL-3.0-or-later
"""Application dialog factories.

Standalone dialogs for Settings, About, and Manage Repos that accept
callbacks for state changes rather than referencing the window directly.
"""

import shutil
import subprocess
import threading
import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # type: ignore # noqa: E402

from termux_appstore.backend.distro import check_package_installed
from termux_appstore.constants import APP_NAME, APP_VERSION

# ---------------------------------------------------------------------------
# About dialog
# ---------------------------------------------------------------------------


def show_about_dialog(parent):
    """Show the standard About dialog.

    Args:
        parent: Transient parent window.
    """
    about_dialog = Gtk.AboutDialog(transient_for=parent)
    about_dialog.set_program_name(APP_NAME)
    about_dialog.set_version(APP_VERSION)
    about_dialog.set_comments("A modern graphical package manager for Termux")
    about_dialog.set_copyright("© 2025 Termux Desktop (sabamdarif)")
    about_dialog.set_license_type(Gtk.License.GPL_3_0)
    about_dialog.set_website("https://github.com/sabamdarif/termux-desktop")
    about_dialog.set_website_label("Website (GITHUB)")
    about_dialog.set_logo_icon_name("system-software-install")

    about_dialog.run()
    about_dialog.destroy()


# ---------------------------------------------------------------------------
# Settings dialog
# ---------------------------------------------------------------------------


def show_settings_dialog(parent, get_setting, set_setting):
    """Show the Settings dialog.

    Args:
        parent: Transient parent window.
        get_setting: Callable ``(key, default) -> value``.
        set_setting: Callable ``(key, value) -> None``.
    """
    dialog = Gtk.Dialog(title="Settings", transient_for=parent)
    dialog.set_default_size(450, 350)

    content = dialog.get_content_area()
    content.set_margin_start(20)
    content.set_margin_end(20)
    content.set_margin_top(20)
    content.set_margin_bottom(20)
    content.set_spacing(16)

    settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

    title_label = Gtk.Label(label="<b>Application Settings</b>")
    title_label.set_use_markup(True)
    title_label.set_halign(Gtk.Align.START)
    title_label.set_margin_bottom(10)
    settings_box.pack_start(title_label, False, False, 0)

    # Setting rows
    _SETTINGS = [
        ("use_terminal_for_progress", "Use terminal for progress", False),
        ("enable_auto_refresh", "Enable auto-refresh", True),
        ("show_command_output", "Show command output in terminal", False),
        ("enable_fuzzy_search", "Enable fuzzy search", False),
    ]

    for key, label_text, default in _SETTINGS:
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_margin_start(12)
        row.set_margin_end(12)
        row.set_margin_top(12)
        row.set_margin_bottom(12)

        label = Gtk.Label(label=label_text)
        label.set_halign(Gtk.Align.START)

        switch = Gtk.Switch()
        switch.set_halign(Gtk.Align.END)
        switch.set_active(get_setting(key, default))

        # Capture *key* in closure
        switch.connect(
            "state-set",
            lambda sw, state, k=key: (
                set_setting(k, state),
                print(f"{k} changed to: {state}"),
            ),
        )

        row.pack_start(label, True, True, 0)
        row.pack_start(switch, False, False, 0)
        frame.add(row)
        settings_box.pack_start(frame, False, False, 0)

    content.pack_start(settings_box, True, True, 0)

    dialog.add_button("Close", Gtk.ResponseType.CLOSE)
    dialog.connect("response", lambda d, r: d.destroy())

    dialog.show_all()
    dialog.run()
    dialog.destroy()


# ---------------------------------------------------------------------------
# Manage Repos dialog
# ---------------------------------------------------------------------------

_REPOS = [
    {
        "name": "x11-repo",
        "label": "X11 Repository",
        "desc": "Package repository containing X11 programs and libraries",
    },
    {
        "name": "root-repo",
        "label": "Root Repository",
        "desc": "Package repository containing programs for rooted devices",
    },
    {
        "name": "tur-repo",
        "label": "TUR Repository",
        "desc": "A single and trusted place for all unofficial/less popular termux packages",
    },
    {
        "name": "glibc-repo",
        "label": "Glibc Repository",
        "desc": "A package repository containing glibc-based programs and libraries",
    },
]


def show_repos_dialog(parent, create_progress_dialog, update_terminal):
    """Show the Manage Repositories dialog.

    Args:
        parent: Transient parent window.
        create_progress_dialog: Factory callable
            ``(title, allow_cancel) -> (dialog, status_label,
            progress_bar, terminal_view)``.
        update_terminal: Callable ``(terminal_view, text) -> None``.
    """
    repo_dialog = Gtk.Dialog(title="Manage Repositories", transient_for=parent)
    repo_dialog.set_default_size(400, 450)
    repo_dialog.set_modal(True)

    content = repo_dialog.get_content_area()
    content.set_margin_start(20)
    content.set_margin_end(20)
    content.set_margin_top(20)
    content.set_margin_bottom(20)
    content.set_spacing(15)

    desc_label = Gtk.Label(label="Select repositories to enable or disable.")
    desc_label.set_halign(Gtk.Align.START)
    desc_label.get_style_context().add_class("dim-label")
    content.pack_start(desc_label, False, False, 0)

    list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    content.pack_start(list_box, True, True, 0)

    # ---- toggled handler ----
    def on_repo_toggled(button, repo_name, label_name):
        is_active = button.get_active()

        pkg_manager = "apt"
        if shutil.which("pacman"):
            pkg_manager = "pacman"

        action = "install" if is_active else "remove"
        action_display = "Installing" if is_active else "Removing"

        if pkg_manager == "apt":
            cmd = f"apt {action} {repo_name} -y"
        else:
            cmd = (
                f"pacman -Syu {repo_name} --noconfirm"
                if is_active
                else f"pacman -R {repo_name} --noconfirm"
            )

        repo_dialog.destroy()

        progress_dialog, status_label, progress_bar, terminal_view = (
            create_progress_dialog(
                title=f"{action_display} {label_name}", allow_cancel=False
            )
        )
        progress_dialog.show_all()

        def _thread():
            try:
                GLib.idle_add(
                    lambda: update_terminal(terminal_view, f"Running: {cmd}\n\n")
                )
                process = subprocess.Popen(
                    ["bash", "-c", cmd],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1,
                )
                if process.stdout:
                    for line in process.stdout:
                        GLib.idle_add(
                            lambda log_line=line: update_terminal(
                                terminal_view, log_line
                            )
                        )
                        GLib.idle_add(progress_bar.pulse)

                process.wait()

                if process.returncode == 0:
                    GLib.idle_add(
                        lambda: update_terminal(
                            terminal_view,
                            f"\nSUCCESS: {label_name} {action}ed successfully.\n",
                        )
                    )
                    GLib.idle_add(
                        status_label.set_text,
                        f"{label_name} {action}ed successfully",
                    )
                    GLib.idle_add(progress_bar.set_fraction, 1.0)
                    time.sleep(1.5)
                    GLib.idle_add(progress_dialog.destroy)
                else:
                    GLib.idle_add(
                        lambda: update_terminal(
                            terminal_view,
                            f"\nERROR: Failed to {action} {label_name}.\n",
                        )
                    )
                    GLib.idle_add(
                        status_label.set_text, f"Failed to {action} {label_name}"
                    )
            except Exception as err:
                GLib.idle_add(
                    lambda e=err: update_terminal(terminal_view, f"\nError: {e}\n")
                )

            # Re-open dialog to refresh state
            GLib.idle_add(
                lambda: show_repos_dialog(
                    parent, create_progress_dialog, update_terminal
                )
            )

        threading.Thread(target=_thread, daemon=True).start()
        progress_dialog.run()

    # ---- build rows ----
    for repo in _REPOS:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        check = Gtk.CheckButton()
        check.set_active(check_package_installed(repo["name"]))

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lbl = Gtk.Label(label=repo["label"])
        lbl.set_halign(Gtk.Align.START)
        lbl.get_style_context().add_class("bold-label")

        desc = Gtk.Label(label=repo["desc"])
        desc.set_halign(Gtk.Align.START)
        desc.get_style_context().add_class("dim-label")
        desc.set_line_wrap(True)

        vbox.pack_start(lbl, False, False, 0)
        vbox.pack_start(desc, False, False, 0)

        row.pack_start(check, False, False, 0)
        row.pack_start(vbox, True, True, 0)
        list_box.pack_start(row, False, False, 0)

        # Connect after setting initial state to avoid initial firing
        check.connect(
            "toggled",
            lambda btn, rn=repo["name"], rl=repo["label"]: on_repo_toggled(btn, rn, rl),
        )

    # Close button
    button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    button_box.set_halign(Gtk.Align.END)
    close_btn = Gtk.Button(label="Close")
    close_btn.connect("clicked", lambda x: repo_dialog.destroy())
    button_box.pack_start(close_btn, False, False, 0)
    content.pack_start(button_box, False, False, 0)

    repo_dialog.show_all()
    repo_dialog.run()
    repo_dialog.destroy()
