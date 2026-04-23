# SPDX-License-Identifier: GPL-3.0-or-later
"""Main application window — orchestrates all extracted modules.

This is the integration layer that wires together the backend, UI,
terminal, and task modules into a working application window.
"""

import os
import platform
import queue
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # type: ignore # noqa: E402

# Backend
from termux_appstore.backend.app_data import load_app_metadata
from termux_appstore.backend.distro import DistroConfig
from termux_appstore.backend.installed_apps import InstalledApps
from termux_appstore.backend.refresh import migrate_old_data, refresh_data
from termux_appstore.backend.settings import Settings
from termux_appstore.backend.updates import UpdateTracker

# Constants & utils
from termux_appstore.constants import (
    APP_NAME,
    APPSTORE_DIR,
    APPSTORE_JSON,
    APPSTORE_LOGO_DIR,
    APPSTORE_OLD_JSON_DIR,
)

# Tasks
from termux_appstore.tasks.task_manager import (
    create_progress_dialog,
    parse_progress_line,
    update_terminal,
)

# Terminal
from termux_appstore.terminal import CommandOutputWindow, show_command_output

# UI widgets
from termux_appstore.ui.app_card import build_app_card
from termux_appstore.ui.dialogs import (
    show_about_dialog,
    show_repos_dialog,
    show_settings_dialog,
)
from termux_appstore.ui.header import build_header_bar, build_menu_popover
from termux_appstore.ui.search import SearchBar
from termux_appstore.ui.sidebar import build_sidebar
from termux_appstore.utils import get_current_arch

# Fuzzy search (optional)
try:
    from fuzzywuzzy import fuzz, process  # type: ignore
except ImportError:
    try:
        from thefuzz import fuzz, process  # type: ignore
    except ImportError:
        fuzz = None
        process = None


class AppStoreWindow(Gtk.ApplicationWindow):
    """Main window that composes all extracted modules."""

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self, app):
        Gtk.ApplicationWindow.__init__(self, application=app, title=APP_NAME)

        # Settings
        self.settings_mgr = Settings()

        # State flags
        self.is_refreshing = False
        self.connectivity_dialog_active = False
        self.cancellation_in_progress = False
        self.installation_cancelled = False
        self.uninstallation_cancelled = False
        self.current_installation = None
        self.update_in_progress = False
        self.logging_active = False
        self.log_file = None
        self.log_file_path = None

        # Architecture
        self.system_arch = get_current_arch()

        # Data managers
        self.installed_tracker = InstalledApps()
        self.installed_apps = self.installed_tracker.apps
        self.update_tracker = UpdateTracker()
        self.pending_updates = self.update_tracker.pending

        # App data
        self.categories = []
        self.apps_data = []

        # Distro
        self.distro_config = DistroConfig()
        self.selected_distro = self.distro_config.selected_distro
        self.distro_enabled = self.distro_config.distro_enabled

        # Task queue
        self.task_queue = queue.Queue()
        self.task_running = False
        self.task_thread = None

        # Window setup
        self.set_default_size(1000, 650)
        self.set_position(Gtk.WindowPosition.CENTER)
        icon_theme = Gtk.IconTheme.get_default()
        if icon_theme.has_icon("system-software-install"):
            self.set_icon_name("system-software-install")
        self.set_wmclass("termux-appstore", APP_NAME)

        # Keyboard accelerators
        accel = Gtk.AccelGroup()
        self.add_accel_group(accel)
        key, mod = Gtk.accelerator_parse("<Control>f")
        accel.connect(key, mod, Gtk.AccelFlags.VISIBLE, self._on_search_accel)
        key, mod = Gtk.accelerator_parse("<Control>q")
        accel.connect(key, mod, Gtk.AccelFlags.VISIBLE, self._on_quit_accel)

        try:
            self._load_css()
            self._build_ui()
            self._start_task_processor()
            self.connect("delete-event", self.on_delete_event)
            self.show_all()
            self._setup_directories()
        except Exception as e:
            print(f"Error during initialization: {e}")
            self._show_error(f"Failed to initialize app store: {e}")
            raise

    # ------------------------------------------------------------------
    # CSS
    # ------------------------------------------------------------------

    def _load_css(self):
        screen = Gdk.Screen.get_default()
        css_provider = Gtk.CssProvider()
        css_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "style", "style.css"
        )
        css_file = os.path.normpath(css_file)
        try:
            css_provider.load_from_path(css_file)
            Gtk.StyleContext.add_provider_for_screen(
                screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception as e:
            print(f"Warning: CSS error: {e}")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Build the complete UI from extracted modules."""
        # Header bar
        hdr = build_header_bar(
            on_section_clicked=self.on_section_clicked,
            on_menu_clicked=self._on_menu_clicked,
            on_search_toggled=self._on_search_toggled,
        )
        self.set_titlebar(hdr["header"])
        self.explore_button = hdr["explore_button"]
        self.installed_button = hdr["installed_button"]
        self.updates_button = hdr["updates_button"]
        self.search_button = hdr["search_button"]
        self.header_tabs_box = hdr["tabs_box"]

        # Main stack (content vs spinner)
        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.main_stack.set_transition_duration(150)
        self.add(self.main_stack)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_stack.add_named(self.main_box, "content")

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.main_box.pack_start(self.content_box, True, True, 0)

        # Spinner page
        spinner_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        spinner_page.set_valign(Gtk.Align.CENTER)
        spinner_page.set_halign(Gtk.Align.CENTER)
        self.main_stack.add_named(spinner_page, "spinner")

        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(64, 64)
        spinner_page.pack_start(self.spinner, False, False, 0)

        self.loading_label = Gtk.Label(
            label="This process will take some time. Please wait..."
        )
        self.loading_label.set_margin_top(10)
        spinner_page.pack_start(self.loading_label, False, False, 0)

        self.main_stack.set_visible_child_name("content")

    # ------------------------------------------------------------------
    # Settings proxies
    # ------------------------------------------------------------------

    def get_setting(self, key, default=None):
        return self.settings_mgr.get(key, default)

    def set_setting(self, key, value):
        self.settings_mgr.set(key, value)

    # ------------------------------------------------------------------
    # Directory setup + data loading
    # ------------------------------------------------------------------

    def _setup_directories(self):
        os.makedirs(APPSTORE_DIR, exist_ok=True)
        os.makedirs(APPSTORE_LOGO_DIR, exist_ok=True)
        os.makedirs(APPSTORE_OLD_JSON_DIR, exist_ok=True)

        if not os.path.exists(APPSTORE_JSON):
            print("First time setup: Initializing app store...")
            self._start_refresh()
        else:
            self._load_and_display()

    def _load_and_display(self):
        """Load metadata and set up the app list UI."""
        self.apps_data, self.categories = load_app_metadata()

        self._setup_app_list_ui()

    def _setup_app_list_ui(self):
        """Build sidebar + right panel from extracted modules."""
        # Architecture warning
        if self.system_arch not in ("arm64", "aarch64"):
            warning = Gtk.InfoBar()
            warning.set_message_type(Gtk.MessageType.WARNING)
            warning.set_show_close_button(True)
            warning.connect("response", lambda bar, r: bar.destroy())
            wbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            wbox.pack_start(
                Gtk.Image.new_from_icon_name("dialog-warning", Gtk.IconSize.MENU),
                False,
                False,
                0,
            )
            lbl = Gtk.Label()
            lbl.set_markup(
                f"Architecture <b>{self.system_arch}</b> might have compatibility issues"
            )
            wbox.pack_start(lbl, False, False, 0)
            warning.get_content_area().add(wbox)
            self.main_box.pack_start(warning, False, False, 0)
            warning.show_all()

        # Sidebar
        sb = build_sidebar(self.categories, self._on_category_clicked)
        self.sidebar = sb["sidebar"]
        self.category_buttons = sb["category_buttons"]
        self.content_box.pack_start(self.sidebar, False, True, 0)

        # Right panel
        self.right_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.content_box.pack_start(self.right_panel, True, True, 0)

        # Search bar
        self.search_bar = SearchBar(
            on_search=self._do_search,
            on_activate=lambda e: (
                self.app_list_box.grab_focus()
                if hasattr(self, "app_list_box")
                else None
            ),
        )
        self.search_box = self.search_bar.box
        self.search_entry = self.search_bar.entry
        self.right_panel.pack_start(self.search_box, False, True, 0)

        # System update button (hidden by default)
        self.update_button = Gtk.Button(label="Check for Updates")
        self.update_button.get_style_context().add_class("system-update-button")
        self.update_button.set_margin_top(10)
        self.update_button.set_margin_start(10)
        self.update_button.set_margin_end(10)
        self.update_button.set_margin_bottom(10)
        self.update_button.hide()
        self.right_panel.pack_start(self.update_button, False, False, 0)

        # Scrolled app list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        self.right_panel.pack_start(scrolled, True, True, 0)

        self.app_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.app_list_box.set_margin_start(10)
        self.app_list_box.set_margin_end(10)
        self.app_list_box.set_margin_top(10)
        self.app_list_box.set_margin_bottom(10)
        scrolled.add(self.app_list_box)

        self.show_apps(None)
        self.content_box.show_all()
        self.update_button.hide()

    # ------------------------------------------------------------------
    # App display
    # ------------------------------------------------------------------

    def show_apps(self, category=None):
        """Display apps filtered by category and search text."""
        try:
            self._clear_app_list()
            filtered = list(self.apps_data)

            if category and category != "All Apps":
                filtered = [a for a in filtered if category in a.get("categories", [])]

            search_text = self.search_bar.text if hasattr(self, "search_bar") else ""
            if search_text:
                filtered = self._apply_search_filter(filtered, search_text)

            if filtered:
                for app in filtered:
                    GLib.idle_add(lambda a=app: self._add_app_card(a))
            else:
                GLib.idle_add(self._show_no_apps_message, search_text)

            GLib.idle_add(self.app_list_box.show_all)
        except Exception as e:
            print(f"Error in show_apps: {e}")

    def show_installed_apps(self):
        """Show only installed apps."""
        self._clear_app_list()
        installed = [
            a for a in self.apps_data if a.get("folder_name") in self.installed_apps
        ]
        search_text = self.search_bar.text if hasattr(self, "search_bar") else ""
        if search_text:
            installed = self._apply_search_filter(installed, search_text)
        for app in installed:
            GLib.idle_add(lambda a=app: self._add_app_card(a))
        if not installed:
            GLib.idle_add(self._show_no_apps_message, search_text)
        GLib.idle_add(self.app_list_box.show_all)

    def show_update_apps(self):
        """Show apps with pending updates."""
        self._clear_app_list()
        updates = [
            a for a in self.apps_data if a.get("folder_name") in self.pending_updates
        ]
        search_text = self.search_bar.text if hasattr(self, "search_bar") else ""
        if search_text:
            updates = self._apply_search_filter(updates, search_text)
        for app in updates:
            GLib.idle_add(lambda a=app: self._add_app_card(a))
        if not updates:
            GLib.idle_add(self._show_no_apps_message, search_text)
        GLib.idle_add(self.app_list_box.show_all)

    def _add_app_card(self, app):
        """Add a single app card using the extracted widget factory."""
        is_installed = app.get("folder_name") in self.installed_apps
        has_update = app.get("folder_name") in self.pending_updates

        card = build_app_card(
            app,
            is_installed=is_installed,
            has_update=has_update,
            on_install=self.on_install_clicked,
            on_uninstall=self.on_uninstall_clicked,
            on_open=self.on_open_clicked,
            on_update=self.on_update_clicked,
        )
        if card:
            self.app_list_box.pack_start(card, False, True, 0)

    def _clear_app_list(self):
        if not hasattr(self, "app_list_box"):
            return
        for child in self.app_list_box.get_children():
            self.app_list_box.remove(child)

    def _show_no_apps_message(self, search_text):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        icon = Gtk.Image.new_from_icon_name("system-search", Gtk.IconSize.DIALOG)
        box.pack_start(icon, False, False, 0)
        if search_text:
            lbl = Gtk.Label()
            lbl.set_markup(
                f"<span size='larger'>No apps match: "
                f"<i>{GLib.markup_escape_text(search_text)}</i></span>"
            )
            box.pack_start(lbl, False, False, 0)
        else:
            lbl = Gtk.Label()
            lbl.set_markup("<span size='larger'>No apps available</span>")
            box.pack_start(lbl, False, False, 0)
        self.app_list_box.pack_start(box, True, True, 0)

    def _apply_search_filter(self, apps, search_text):
        if self.get_setting("enable_fuzzy_search", False) and fuzz:
            threshold = 60
            scored = []
            for app in apps:
                ns = fuzz.partial_ratio(search_text, app["app_name"].lower())
                ds = fuzz.partial_ratio(search_text, app.get("description", "").lower())
                cs = max(
                    (
                        fuzz.partial_ratio(search_text, c.lower())
                        for c in app.get("categories", [])
                    ),
                    default=0,
                )
                best = max(ns, ds, cs)
                if best >= threshold:
                    scored.append((app, best))
            scored.sort(key=lambda x: x[1], reverse=True)
            return [a for a, _ in scored]

        name_matches = [a for a in apps if search_text in a["app_name"].lower()]
        if name_matches:
            return name_matches
        desc = [a for a in apps if search_text in a.get("description", "").lower()]
        cat = [
            a
            for a in apps
            if any(search_text in c.lower() for c in a.get("categories", []))
        ]
        return list({a["app_name"]: a for a in desc + cat}.values())

    # ------------------------------------------------------------------
    # Header / section handlers
    # ------------------------------------------------------------------

    def on_section_clicked(self, button, section):
        self.current_section = section
        for btn in (self.explore_button, self.installed_button, self.updates_button):
            btn.get_style_context().remove_class("selected")
            btn.get_style_context().remove_class("active")
        if button:
            button.get_style_context().add_class("selected")
            button.get_style_context().add_class("active")

        if hasattr(self, "search_bar"):
            self.search_box.hide()
            self.search_button.set_image(
                Gtk.Image.new_from_icon_name(
                    "system-search-symbolic", Gtk.IconSize.BUTTON
                )
            )
            self.search_entry.set_text("")

        if not hasattr(self, "app_list_box"):
            GLib.timeout_add(100, lambda: self.on_section_clicked(button, section))
            return

        self._clear_app_list()

        if section == "explore":
            if hasattr(self, "sidebar"):
                self.sidebar.show()
            self.update_button.hide()
            sel_cat = None
            if hasattr(self, "category_buttons"):
                for cb in self.category_buttons:
                    if cb.get_style_context().has_class("selected"):
                        sel_cat = cb.get_label()
                        break
            if sel_cat == "All Apps":
                sel_cat = None
            self.show_apps(sel_cat)
        elif section == "installed":
            if hasattr(self, "sidebar"):
                self.sidebar.hide()
            self.update_button.hide()
            self.show_installed_apps()
        elif section == "updates":
            if hasattr(self, "sidebar"):
                self.sidebar.hide()
            self.update_button.show()
            self.show_update_apps()

    def _on_menu_clicked(self, button):
        build_menu_popover(
            button,
            on_about=lambda w: show_about_dialog(self),
            on_repos=lambda w: show_repos_dialog(
                self, self._create_progress_dialog, self._update_terminal
            ),
            on_settings=lambda w: show_settings_dialog(
                self, self.get_setting, self.set_setting
            ),
            on_quit=lambda w: self.on_delete_event(None, None),
        )

    def _on_search_toggled(self, button):
        if hasattr(self, "search_bar"):
            self.search_bar.toggle(self.search_button)

    def _on_category_clicked(self, button):
        for btn in self.category_buttons:
            btn.get_style_context().remove_class("selected")
        button.get_style_context().add_class("selected")
        cat = button.get_label()
        self.show_apps(None if cat == "All Apps" else cat)

    def _get_selected_category(self):
        """Return the currently highlighted sidebar category, or None."""
        if not hasattr(self, "category_buttons"):
            return None
        for btn in self.category_buttons:
            if btn.get_style_context().has_class("selected"):
                label = btn.get_label()
                return None if label == "All Apps" else label
        return None

    def _do_search(self, search_text):
        section = getattr(self, "current_section", "explore")
        if section == "explore":
            sel_cat = None
            for btn in self.category_buttons:
                if btn.get_style_context().has_class("selected"):
                    sel_cat = btn.get_label()
                    break
            if sel_cat == "All Apps":
                sel_cat = None
            self.show_apps(sel_cat)
        elif section == "installed":
            self.show_installed_apps()
        elif section == "updates":
            self.show_update_apps()

    # ------------------------------------------------------------------
    # Accelerators
    # ------------------------------------------------------------------

    def _on_search_accel(self, *args):
        self._on_search_toggled(None)
        return True

    def _on_quit_accel(self, *args):
        self.on_delete_event(None, None)
        return True

    # ------------------------------------------------------------------
    # Action handlers (install / uninstall / open / update)
    # ------------------------------------------------------------------

    def on_install_clicked(self, button, app):
        """Handle install button — runs install script in a background thread."""
        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Install {app['app_name']}?",
        )
        response = dlg.run()
        dlg.destroy()
        if response != Gtk.ResponseType.YES:
            return

        self._run_script_thread(
            app,
            url_key="install_url",
            action_label="Installing",
            on_success=lambda: self._mark_installed(app, True),
        )

    def on_uninstall_clicked(self, button, app):
        """Handle uninstall button — runs uninstall script in a background thread."""
        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Uninstall {app['app_name']}?",
        )
        response = dlg.run()
        dlg.destroy()
        if response != Gtk.ResponseType.YES:
            return

        uninstall_url = app.get("uninstall_url") or app.get("uninstall_script")
        if not uninstall_url:
            self._show_error("No uninstall script available for this app!")
            return

        self._run_script_thread(
            app,
            url_key="uninstall_url",
            fallback_url_key="uninstall_script",
            action_label="Uninstalling",
            on_success=lambda: self._mark_installed(app, False),
        )

    def on_open_clicked(self, button, app):
        """Handle open button."""
        run_cmd = app.get("run_cmd", "")
        if not run_cmd:
            self._show_error("No run command specified for this app")
            return
        if app.get("app_type") == "distro":
            run_cmd = f"pdrun {run_cmd}"
        if self.get_setting("show_command_output", False):
            show_command_output(run_cmd, app.get("app_name", "App"), self)
        else:
            subprocess.Popen(["bash", "-c", run_cmd])

    def on_update_clicked(self, button, app):
        """Handle update button — re-installs the app."""
        self.on_install_clicked(button, app)

    # ------------------------------------------------------------------
    # Shared script execution engine
    # ------------------------------------------------------------------

    def _run_script_thread(
        self, app, url_key, action_label, on_success, fallback_url_key=None
    ):
        """Download and execute an install/uninstall script.

        Shows a progress dialog with terminal output and weighted
        progress tracking.  Runs the script on a daemon thread.
        """
        import os
        import signal
        import stat
        import time

        from termux_appstore.backend.script_runner import download_script

        url = app.get(url_key) or (
            app.get(fallback_url_key) if fallback_url_key else None
        )
        if not url:
            self._show_error(f"No {url_key} available for this app!")
            return

        progress_dialog, status_label, progress_bar, terminal_view = (
            self._create_progress_dialog(
                title=f"{action_label}...", allow_cancel=True, use_terminal=True
            )
        )

        cancelled = False
        process = None
        script_file = None

        # --- Cancel handler ---
        def on_cancel(*_args):
            nonlocal cancelled
            cancelled = True
            if process:
                try:
                    pgid = os.getpgid(process.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(pgid, signal.SIGKILL)
                        process.wait(timeout=1)
                except Exception as e:
                    print(f"Error stopping process: {e}")
            GLib.timeout_add(
                500, lambda: progress_dialog.destroy() if progress_dialog else None
            )
            return True

        progress_dialog.connect("response", on_cancel)

        # --- Progress helper ---
        def update_progress(fraction, text):
            if not progress_dialog or not progress_dialog.get_window():
                return False
            status_label.set_text(text)
            progress_bar.set_fraction(fraction)
            progress_bar.set_text(f"{int(fraction * 100)}%")
            return False

        # --- Weight-based progress constants ---
        function_weights = {
            "package_install_and_check": 50,
            "package_remove_and_check": 30,
            "install_appimage": 30,
            "download_file": 20,
            "extract": 15,
            "distro_run": 25,
            "check_and_create_directory": 2,
            "check_and_delete": 2,
            "check_and_backup": 2,
            "check_and_restore": 2,
            "echo": 1,
        }
        default_weight = 5

        def worker():
            nonlocal script_file, process

            try:
                # 1. Download script (20%)
                GLib.idle_add(
                    update_progress,
                    0.2,
                    f"Downloading {action_label.lower()} script...",
                )
                GLib.idle_add(
                    lambda: update_terminal(
                        terminal_view, f"Downloading {action_label.lower()} script...\n"
                    )
                )
                script_file = download_script(url)
                if not script_file or cancelled:
                    if script_file and os.path.exists(script_file):
                        os.remove(script_file)
                    GLib.idle_add(progress_dialog.destroy)
                    return

                # 2. Make executable (30%)
                GLib.idle_add(
                    update_progress, 0.3, f"Preparing {action_label.lower()}..."
                )
                os.chmod(script_file, os.stat(script_file).st_mode | stat.S_IEXEC)

                # 3. Analyse script for progress weighting
                total_weight = 0
                try:
                    with open(script_file, "r") as f:
                        for raw_line in f:
                            raw_line = raw_line.strip()
                            if raw_line and not raw_line.startswith("#"):
                                weight = default_weight
                                for func, w in function_weights.items():
                                    if func in raw_line:
                                        weight = w
                                        break
                                else:
                                    if (
                                        "apt install" in raw_line
                                        or "pacman -" in raw_line
                                    ):
                                        weight = 40
                                total_weight += weight
                except Exception:
                    total_weight = 100

                total_weight = max(1, total_weight)

                GLib.idle_add(
                    lambda: update_terminal(
                        terminal_view, f"Script analysis: total weight {total_weight}\n"
                    )
                )

                # 4. Run script
                start_progress = 0.15
                end_progress = 0.95
                progress_range = end_progress - start_progress
                completed_weight = 0
                current_op_weight = 0
                current_op_progress = 0.0

                GLib.idle_add(
                    update_progress,
                    start_progress,
                    f"Starting {action_label.lower()}...",
                )
                process = subprocess.Popen(
                    ["bash", script_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1,
                    preexec_fn=os.setsid,
                )

                while True:
                    if cancelled:
                        GLib.idle_add(progress_dialog.destroy)
                        return

                    line = process.stdout.readline() if process.stdout else ""
                    if not line and process.poll() is not None:
                        break

                    line = line.strip()
                    if not line:
                        continue

                    # Check for progress protocol lines
                    progress_info = parse_progress_line(line)
                    if progress_info:
                        try:
                            val_str = progress_info["value"]
                            if "/" in val_str:
                                curr, tot = val_str.split("/")
                                sub = float(curr) / max(1, float(tot))
                            else:
                                sub = float(val_str) / 100.0
                        except (ValueError, TypeError):
                            sub = 0.5

                        current_op_progress = sub
                        eff_w = (
                            current_op_weight
                            if current_op_weight > 0
                            else default_weight
                        )
                        wp = (
                            completed_weight + eff_w * current_op_progress
                        ) / total_weight
                        cp = min(end_progress, start_progress + wp * progress_range)
                        GLib.idle_add(update_progress, cp, progress_info["message"])
                        GLib.idle_add(
                            lambda l=line: update_terminal(terminal_view, l + "\n")
                        )
                        continue

                    # Detect heavyweight operation starts
                    for func, w in function_weights.items():
                        if func in line:
                            if current_op_weight > 0:
                                completed_weight += current_op_weight
                            current_op_weight = w
                            current_op_progress = 0.0
                            break

                    eff_w = (
                        current_op_weight if current_op_weight > 0 else default_weight
                    )
                    wp = (completed_weight + eff_w * current_op_progress) / total_weight
                    cp = min(end_progress, start_progress + wp * progress_range)
                    GLib.idle_add(update_progress, cp, line)
                    GLib.idle_add(
                        lambda l=line: update_terminal(terminal_view, l + "\n")
                    )

                # 5. Handle result
                if process.wait() == 0 and not cancelled:
                    GLib.idle_add(
                        update_progress, 0.95, f"Finalizing {action_label.lower()}..."
                    )
                    GLib.idle_add(on_success)

                    # Refresh the visible app list
                    cat = self._get_selected_category()
                    GLib.idle_add(lambda c=cat: self.show_apps(c))

                    GLib.idle_add(update_progress, 1.0, f"{action_label} complete!")
                    time.sleep(2)
                else:
                    if not cancelled:
                        GLib.idle_add(update_progress, 1.0, f"{action_label} failed!")
                        time.sleep(2)

                GLib.idle_add(progress_dialog.destroy)

            except Exception as e:
                print(f"{action_label} error: {e}")
                GLib.idle_add(update_progress, 1.0, f"Error: {e}")
                time.sleep(2)
                GLib.idle_add(progress_dialog.destroy)

            finally:
                if process:
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    except Exception:
                        pass
                    process = None
                if script_file and os.path.exists(script_file):
                    try:
                        os.remove(script_file)
                    except Exception:
                        pass

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _mark_installed(self, app, installed):
        """Update installed status for *app* and persist."""
        folder = app["folder_name"]
        self.installed_tracker.update_status(folder, installed)
        self.installed_apps = self.installed_tracker.apps

        if not installed and folder in self.pending_updates:
            del self.pending_updates[folder]
            self.update_tracker.pending = self.pending_updates

    # ------------------------------------------------------------------
    # Progress dialog proxies
    # ------------------------------------------------------------------

    def _create_progress_dialog(
        self, title="Installing...", allow_cancel=True, use_terminal=None
    ):
        if use_terminal is None:
            use_terminal = self.get_setting("use_terminal_for_progress", False)
        d, sl, pb, tv, te, ls = create_progress_dialog(
            self, title, allow_cancel, use_terminal
        )
        return d, sl, pb, tv

    def _update_terminal(self, terminal_view, text):
        update_terminal(terminal_view, text)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _start_refresh(self):
        """Run the full refresh pipeline on a background thread."""
        self.is_refreshing = True
        self.main_stack.set_visible_child_name("spinner")
        self.spinner.start()

        # Migrate old data on first run
        migrate_old_data()

        def _refresh_thread():
            success = refresh_data(
                self.installed_tracker,
                self.update_tracker,
                on_error=lambda msg: GLib.idle_add(self._on_refresh_error, msg),
            )
            if success:
                GLib.idle_add(self._on_refresh_complete)

        thread = threading.Thread(target=_refresh_thread, daemon=True)
        thread.start()

    def _on_refresh_complete(self):
        """Called on main thread when refresh succeeds."""
        self.is_refreshing = False
        self.spinner.stop()

        # Reload data from the freshly downloaded apps.json
        self.installed_apps = self.installed_tracker.apps
        self.pending_updates = self.update_tracker.pending
        self._load_and_display()

        self.main_stack.set_visible_child_name("content")
        print("Refresh complete — UI updated")

    def _on_refresh_error(self, message):
        """Called on main thread when refresh fails."""
        self.is_refreshing = False
        self.spinner.stop()
        self.main_stack.set_visible_child_name("content")
        self._show_error(f"Refresh failed: {message}")

    # ------------------------------------------------------------------
    # Task processor
    # ------------------------------------------------------------------

    def _start_task_processor(self):
        self.task_running = True
        self.task_thread = threading.Thread(target=self._process_tasks, daemon=True)
        self.task_thread.start()

    def _process_tasks(self):
        while self.task_running:
            try:
                task = self.task_queue.get(timeout=1.0)
                if task:
                    task()
                self.task_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing task: {e}")

    def _stop_task_processor(self):
        self.task_running = False

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def on_delete_event(self, widget, event):
        try:
            self._stop_task_processor()
            self.installed_tracker.save()
            self.update_tracker.save()
            self.get_application().quit()
        except Exception as e:
            print(f"Error during cleanup: {e}")
        return False

    def _show_error(self, message):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message,
        )
        dlg.run()
        dlg.destroy()
