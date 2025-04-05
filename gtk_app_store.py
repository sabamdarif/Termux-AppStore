#!/data/data/com.termux/files/usr/bin/python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango, Gio
import os
import json
import subprocess
from pathlib import Path
import stat
import time
from datetime import datetime, timedelta
import threading
import sys
import queue
import shutil
from PIL import Image
import platform
from concurrent.futures import ThreadPoolExecutor
import signal
import re
import tempfile
import logging
import traceback
import urllib.request
import tarfile
import zipfile
import random
import fcntl
import socket

# Fuzzy search libraries
try:
    from fuzzywuzzy import fuzz, process
except ImportError:
    try:
        from thefuzz import fuzz, process
    except ImportError:
        print("Warning: Fuzzy search libraries not found. Falling back to regular search.")
        fuzz = None
        process = None

# Termux-specific paths
TERMUX_PREFIX = "/data/data/com.termux/files/usr"
TERMUX_TMP = os.path.join(TERMUX_PREFIX, "tmp")

# App store paths
APPSTORE_DIR = os.path.expanduser("~/.appstore")
APPSTORE_LOGO_DIR = os.path.join(APPSTORE_DIR, "logo")
APPSTORE_JSON = os.path.join(APPSTORE_DIR, "apps.json")
LAST_REFRESH_FILE = os.path.join(APPSTORE_DIR, "last_refresh")
GITHUB_APPS_JSON = "https://raw.githubusercontent.com/sabamdarif/Termux-AppStore/main/data/apps.json"

# Add these constants after the existing path definitions
APPSTORE_OLD_JSON_DIR = os.path.join(APPSTORE_DIR, 'old_json')
UPDATES_TRACKING_FILE = os.path.join(APPSTORE_DIR, "updates.json")  # Changed from .termux_appstore
INSTALLED_APPS_FILE = os.path.join(APPSTORE_DIR, "installed_apps.json")  # Changed from .termux_appstore
LAST_VERSION_CHECK_FILE = os.path.join(APPSTORE_DIR, "last_version_check")  # Changed from .termux_appstore
SETTINGS_FILE = os.path.join(APPSTORE_DIR, "settings.json")  # User settings file

# Function to validate logo size
def validate_logo_size(logo_path):
    """Check if the logo is within the required size range."""
    try:
        with Image.open(logo_path) as img:
            width, height = img.size
            if 20 <= width <= 180 and 20 <= height <= 180:
                return True
            else:
                print(f"Logo for {os.path.basename(logo_path)} is not within the required size range (20x20 to 180x180).")
                return False
    except Exception as e:
        print(f"Error validating logo size for {logo_path}: {e}")
        return False

class AppStoreApplication(Gtk.Application):
    def __init__(self):
        """Initialize the application"""
        Gtk.Application.__init__(
            self,
            application_id="org.sabamdarif.termux.appstore",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self.window = None
        # Connect the activate signal
        self.connect('activate', self.on_activate)

    def do_startup(self):
        """Application startup"""
        Gtk.Application.do_startup(self)
        # Set application name
        GLib.set_application_name("Termux AppStore")
        # Set the application icon
        icon_theme = Gtk.IconTheme.get_default()
        try:
            icon = icon_theme.load_icon("org.gnome.Software", 128, 0)
            Gtk.Window.set_default_icon(icon)
        except Exception as e:
            print(f"Failed to set application icon: {e}")

    def on_activate(self, app):
        """Called when the application is activated"""
        # Check if window exists already and just present it
        if self.window:
            self.window.present()
            return
            
        # Create a new window if one doesn't exist
        self.window = AppStoreWindow(self)
        self.window.present()

class AppStoreWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        """Initialize window"""
        Gtk.ApplicationWindow.__init__(self, application=app, title="Termux App Store")
        
        # Load settings
        self.load_settings()
        self.selected_distro = None
        self.distro_enabled = False
        self.is_refreshing = False  # Add a flag to track refresh state
        self.connectivity_dialog_active = False  # Add flag to prevent multiple connectivity dialogs
        self.cancellation_in_progress = False  # Add flag to track dialog cancellation
        
        # Initialize search variables
        self.search_timeout_id = None
        self.search_delay = 100  # milliseconds
        
        # Set up keyboard accelerators
        accel_group = Gtk.AccelGroup()
        self.add_accel_group(accel_group)
        
        # Add Ctrl+F for search
        key, mod = Gtk.accelerator_parse("<Control>f")
        accel_group.connect(key, mod, Gtk.AccelFlags.VISIBLE, self.on_search_accelerator)
        
        # Add Ctrl+Q for quit
        key, mod = Gtk.accelerator_parse("<Control>q")
        accel_group.connect(key, mod, Gtk.AccelFlags.VISIBLE, self.on_quit_accelerator)
        
        # Set up scaling for hi-dpi screens
        self.set_default_size(1000, 650)
        # Set window position to center
        self.set_position(Gtk.WindowPosition.CENTER)
        
        # Set window icon
        icon_name = "system-software-install"
        icon_theme = Gtk.IconTheme.get_default()
        if icon_theme.has_icon(icon_name):
            self.set_icon_name(icon_name)
        
        # Set window class
        self.set_wmclass("termux-appstore", "Termux AppStore")
        
        # Identify system architecture
        self.system_arch = platform.machine().lower()
        print(f"System architecture: {self.system_arch}")
        
        # Maps system architecture to compatible architectures
        self.arch_compatibility = {
            "aarch64": ["aarch64", "arm64", "arm", "all", "any"],
            "armv8l": ["arm", "armv7", "armhf", "all", "any"],
            "armv7l": ["arm", "armv7", "armhf", "all", "any"],
            "x86_64": ["x86_64", "amd64", "x86", "all", "any"],
            "i686": ["x86", "i686", "i386", "all", "any"]
        }
        
        # Initialize task queue and current task first
        self.task_queue = queue.Queue()
        self.current_task = None
        self.stop_background_tasks = False
        
        # Initialize thread pool
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # Initialize all state flags
        self.installation_cancelled = False
        self.uninstallation_cancelled = False
        self.current_installation = None
        
        # Initialize update state
        self.update_in_progress = False

        # Initialize thread pool and queues
        self.ui_update_queue = queue.Queue()
        self.pending_ui_updates = []
        
        # Initialize updates tracking
        self.updates_tracking_file = UPDATES_TRACKING_FILE
        self.pending_updates = {}
        
        # Initialize installed apps tracking
        self.installed_apps_file = Path(INSTALLED_APPS_FILE)
        self.installed_apps_file.parent.mkdir(parents=True, exist_ok=True)
        self.load_installed_apps()

        # Initialize categories and apps data
        self.categories = []
        self.apps_data = []

        try:
            # Create main UI layout first
            self.create_ui()

            # Start task processor after UI creation
            self.start_task_processor()

            # Connect the delete-event to handle window closing
            self.connect("delete-event", self.on_delete_event)

            # Show all widgets
            self.show_all()

            # Initialize paths and create directories (after UI is ready)
            self.setup_directories()

            # Start the initial data load
            self.check_for_updates()
        except Exception as e:
            print(f"Error during initialization: {e}")
            self.show_error_dialog(f"Failed to initialize app store: {str(e)}")
            raise

    def create_ui(self):
        """Create the main UI for the application"""
        # Set up CSS
        screen = Gdk.Screen.get_default()
        css_provider = Gtk.CssProvider()
        # Try to load CSS, but don't fail if there are errors
        css_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style", "style.css")
        print(f"Loading CSS from: {css_file}")
        try:
            css_provider.load_from_path(str(css_file))
            Gtk.StyleContext.add_provider_for_screen(
                screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except Exception as e:
            print(f"Warning: CSS error occurred: {e}")
            print("Continuing without custom styles")

        try:
            # Create header bar first (so it's always visible)
            header = Gtk.HeaderBar()
            header.set_show_close_button(True)
            header.props.title = "Termux AppStore"
            self.set_titlebar(header)

            # Create box for tabs
            self.header_tabs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            self.header_tabs_box.get_style_context().add_class('header-tabs-box')
            header.set_custom_title(self.header_tabs_box)

            # Create tab buttons with icons
            self.explore_button = self.create_tab_button("Explore", "system-search-symbolic")
            self.installed_button = self.create_tab_button("Installed", "system-software-install-symbolic")
            self.updates_button = self.create_tab_button("Updates", "software-update-available-symbolic")
            
            # Connect click handlers
            self.explore_button.connect("clicked", self.on_section_clicked, "explore")
            self.installed_button.connect("clicked", self.on_section_clicked, "installed")
            self.updates_button.connect("clicked", self.on_section_clicked, "updates")
            
            # Set initial active state - use both classes for compatibility
            self.explore_button.get_style_context().add_class('active')
            self.explore_button.get_style_context().add_class('selected')

            self.header_tabs_box.pack_start(self.explore_button, False, False, 0)
            self.header_tabs_box.pack_start(self.installed_button, False, False, 0)
            self.header_tabs_box.pack_start(self.updates_button, False, False, 0)
            
            # Create menu button
            menu_button = Gtk.Button()
            menu_button.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
            menu_button.get_style_context().add_class('menu-button')
            menu_button.connect("clicked", self.on_menu_clicked)
            header.pack_end(menu_button)
            
            # Create search button to toggle search bar visibility
            self.search_button = Gtk.Button()
            self.search_button.set_image(Gtk.Image.new_from_icon_name("system-search-symbolic", Gtk.IconSize.BUTTON))
            self.search_button.get_style_context().add_class('menu-button')
            self.search_button.set_tooltip_text("Show Search")
            self.search_button.connect("clicked", self.on_search_button_clicked)
            header.pack_end(self.search_button)

            # Create main container as a stack (for showing content or spinner)
            self.main_stack = Gtk.Stack()
            self.main_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
            self.main_stack.set_transition_duration(150)
            self.add(self.main_stack)

            # Create main content box
            self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.main_stack.add_named(self.main_box, "content")
            
            # Create content box for app list
            self.content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            self.main_box.pack_start(self.content_box, True, True, 0)

            # Create spinner page (separate from content)
            spinner_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            spinner_page.set_valign(Gtk.Align.CENTER)
            spinner_page.set_halign(Gtk.Align.CENTER)
            self.main_stack.add_named(spinner_page, "spinner")
            
            # Add spinner and loading text to spinner page
            self.spinner = Gtk.Spinner()
            self.spinner.set_size_request(64, 64)
            spinner_page.pack_start(self.spinner, False, False, 0)
            
            self.loading_label = Gtk.Label(label="This process will take some time. Please wait...")
            self.loading_label.set_margin_top(10)
            spinner_page.pack_start(self.loading_label, False, False, 0)
            
            # Show content by default
            self.main_stack.set_visible_child_name("content")
            
        except Exception as e:
            print(f"Error creating UI: {e}")
            raise

    def create_tab_button(self, label_text, icon_name):
        """Create a styled tab button with icon and label"""
        button = Gtk.Button()
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.get_style_context().add_class("header-tab-button")
        
        # Set fixed size to prevent the button from changing size when text becomes bold
        button.set_size_request(120, 36)
        
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        label = Gtk.Label(label=label_text)
        
        hbox.pack_start(icon, False, False, 0)
        hbox.pack_start(label, False, False, 0)
        button.add(hbox)
        
        return button
        
    def on_menu_clicked(self, button):
        """Show the application menu"""
        popover = Gtk.Popover(relative_to=button)
        popover.set_position(Gtk.PositionType.BOTTOM)
        
        # Create main box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.set_spacing(2)  # Minimal spacing between items
        
        # About item
        about_button = Gtk.ModelButton(label="About")
        about_button.connect("clicked", self.on_about_clicked)
        box.pack_start(about_button, False, False, 0)
        
        # Add a separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(separator, False, False, 6)
        
        # Settings item
        settings_button = Gtk.ModelButton(label="Settings")
        settings_button.connect("clicked", self.on_settings_clicked)
        box.pack_start(settings_button, False, False, 0)
        
        # Add another separator
        separator2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(separator2, False, False, 6)
        
        # Quit item
        quit_button = Gtk.ModelButton(label="Quit")
        quit_button.connect("clicked", self.on_quit_clicked)
        box.pack_start(quit_button, False, False, 0)
        
        # Show the box in the popover
        box.show_all()
        popover.add(box)
        popover.popup()
        
    def on_search_button_clicked(self, button):
        """Toggle the visibility of the search bar"""
        if hasattr(self, 'search_box'):
            if self.search_box.get_visible():
                # Hide search bar
                self.search_box.hide()
                # Update button icon to indicate search is hidden
                self.search_button.set_image(Gtk.Image.new_from_icon_name("system-search-symbolic", Gtk.IconSize.BUTTON))
                self.search_button.set_tooltip_text("Show Search")
            else:
                # Show search bar
                self.search_box.show()
                # Update button icon to indicate search is visible
                self.search_button.set_image(Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.BUTTON))
                self.search_button.set_tooltip_text("Hide Search")
                # Give focus to the search entry
                if hasattr(self, 'search_entry'):
                    self.search_entry.grab_focus()

    def on_settings_clicked(self, widget):
        """Show settings window"""
        settings_dialog = Gtk.Dialog(title="Settings", transient_for=self)
        settings_dialog.set_default_size(450, 350)
        
        # Create main content box
        content_box = settings_dialog.get_content_area()
        content_box.set_margin_start(20)
        content_box.set_margin_end(20)
        content_box.set_margin_top(20)
        content_box.set_margin_bottom(20)
        content_box.set_spacing(16)
        
        # Create settings box
        settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        
        # Add header title
        title_label = Gtk.Label(label="<b>Application Settings</b>")
        title_label.set_use_markup(True)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_margin_bottom(10)
        settings_box.pack_start(title_label, False, False, 0)
        
        # Terminal progress setting
        terminal_frame = Gtk.Frame()
        terminal_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        terminal_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        terminal_box.set_margin_start(12)
        terminal_box.set_margin_end(12)
        terminal_box.set_margin_top(12)
        terminal_box.set_margin_bottom(12)
        
        terminal_label = Gtk.Label(label="Use terminal for progress")
        terminal_label.set_halign(Gtk.Align.START)
        terminal_switch = Gtk.Switch()
        terminal_switch.set_halign(Gtk.Align.END)
        terminal_switch.set_active(self.get_setting("use_terminal_for_progress", False))
        terminal_switch.connect("state-set", self.on_terminal_progress_toggled)
        
        terminal_box.pack_start(terminal_label, True, True, 0)
        terminal_box.pack_start(terminal_switch, False, False, 0)
        terminal_frame.add(terminal_box)
        settings_box.pack_start(terminal_frame, False, False, 0)
        
        # Auto-refresh setting
        refresh_frame = Gtk.Frame()
        refresh_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        refresh_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        refresh_box.set_margin_start(12)
        refresh_box.set_margin_end(12)
        refresh_box.set_margin_top(12)
        refresh_box.set_margin_bottom(12)
        
        refresh_label = Gtk.Label(label="Enable auto-refresh")
        refresh_label.set_halign(Gtk.Align.START)
        refresh_switch = Gtk.Switch()
        refresh_switch.set_halign(Gtk.Align.END)
        refresh_switch.set_active(self.get_setting("enable_auto_refresh", True))
        refresh_switch.connect("state-set", self.on_auto_refresh_toggled)
        
        refresh_box.pack_start(refresh_label, True, True, 0)
        refresh_box.pack_start(refresh_switch, False, False, 0)
        refresh_frame.add(refresh_box)
        settings_box.pack_start(refresh_frame, False, False, 0)
        
        # Show command output setting
        output_frame = Gtk.Frame()
        output_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        output_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        output_box.set_margin_start(12)
        output_box.set_margin_end(12)
        output_box.set_margin_top(12)
        output_box.set_margin_bottom(12)
        
        output_label = Gtk.Label(label="Show command output in terminal")
        output_label.set_halign(Gtk.Align.START)
        output_switch = Gtk.Switch()
        output_switch.set_halign(Gtk.Align.END)
        output_switch.set_active(self.get_setting("show_command_output", False))
        output_switch.connect("state-set", self.on_command_output_toggled)
        
        output_box.pack_start(output_label, True, True, 0)
        output_box.pack_start(output_switch, False, False, 0)
        output_frame.add(output_box)
        settings_box.pack_start(output_frame, False, False, 0)
        
        # Fuzzy search setting
        fuzzy_frame = Gtk.Frame()
        fuzzy_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        fuzzy_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        fuzzy_box.set_margin_start(12)
        fuzzy_box.set_margin_end(12)
        fuzzy_box.set_margin_top(12)
        fuzzy_box.set_margin_bottom(12)
        
        fuzzy_label = Gtk.Label(label="Enable fuzzy search")
        fuzzy_label.set_halign(Gtk.Align.START)
        fuzzy_switch = Gtk.Switch()
        fuzzy_switch.set_halign(Gtk.Align.END)
        fuzzy_switch.set_active(self.get_setting("enable_fuzzy_search", False))
        fuzzy_switch.connect("state-set", self.on_fuzzy_search_toggled)
        
        fuzzy_box.pack_start(fuzzy_label, True, True, 0)
        fuzzy_box.pack_start(fuzzy_switch, False, False, 0)
        fuzzy_frame.add(fuzzy_box)
        settings_box.pack_start(fuzzy_frame, False, False, 0)
        
        # Add settings box to content
        content_box.pack_start(settings_box, True, True, 0)
        
        # Add close button
        settings_dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        settings_dialog.connect("response", lambda dialog, response: dialog.destroy())
        
        settings_dialog.show_all()
        settings_dialog.run()
        settings_dialog.destroy()

    def on_terminal_progress_toggled(self, switch, state):
        """Handle toggle of terminal progress option"""
        self.set_setting("use_terminal_for_progress", state)
        print(f"Terminal progress setting changed to: {state}")
    
    def on_auto_refresh_toggled(self, switch, state):
        """Handle toggle of auto-refresh option"""
        self.set_setting("enable_auto_refresh", state)
        print(f"Auto-refresh setting changed to: {state}")
    
    def on_command_output_toggled(self, switch, state):
        """Handle toggle of command output option"""
        self.set_setting("show_command_output", state)
        print(f"Command output setting changed to: {state}")
    
    def on_fuzzy_search_toggled(self, switch, state):
        """Handle toggle of fuzzy search option"""
        self.set_setting("enable_fuzzy_search", state)
        print(f"Fuzzy search setting changed to: {state}")
    
    def on_about_clicked(self, widget):
        """Show about dialog"""
        about_dialog = Gtk.AboutDialog(transient_for=self)
        
        # Set dialog properties
        about_dialog.set_program_name("Termux App Store")
        about_dialog.set_version("0.5.3")
        about_dialog.set_comments("A modern graphical package manager for Termux")
        about_dialog.set_copyright("© 2025 Termux Desktop (sabamdarif)")
        about_dialog.set_license_type(Gtk.License.GPL_3_0)
        about_dialog.set_website("https://github.com/sabamdarif/termux-desktop")
        about_dialog.set_website_label("Website (GITHUB)")
        about_dialog.set_logo_icon_name("system-software-install")
        
        # Show the dialog
        about_dialog.run()
        about_dialog.destroy()
    
    def on_quit_clicked(self, widget):
        """Handle quit menu item click"""
        # Close any open log files
        if hasattr(self, 'log_file') and self.log_file:
            try:
                self.log_file.write("\n--- Application closed by user ---\n")
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None
            self.logging_active = False
            self.log_file_path = None
            
        self.on_delete_event(None, None)

    def setup_directories(self):
        """Create necessary directories for the app store"""
        try:
            # Set up partial setup detection
            needs_setup = False
            
            # Create main directories
            os.makedirs(APPSTORE_DIR, exist_ok=True)
            
            # Check if other required directories exist
            if not os.path.exists(APPSTORE_LOGO_DIR):
                needs_setup = True
                os.makedirs(APPSTORE_LOGO_DIR, exist_ok=True)
                
            if not os.path.exists(APPSTORE_OLD_JSON_DIR):
                needs_setup = True
                os.makedirs(APPSTORE_OLD_JSON_DIR, exist_ok=True)
            
            # Migrate data from old directory structure if needed
            self.migrate_old_data()
            
            # Check for distro configuration
            self.check_distro_configuration()
            
            # Initialize apps.json if it doesn't exist
            if not os.path.exists(APPSTORE_JSON):
                print("First time setup: Initializing app store...")
                needs_setup = True
            
            # Initialize updates tracking file if it doesn't exist
            if not os.path.exists(self.updates_tracking_file):
                with open(self.updates_tracking_file, 'w') as f:
                    json.dump({}, f)
            
            # Initialize settings file if it doesn't exist
            if not os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'w') as f:
                    json.dump({
                        "use_terminal_for_progress": False,
                        "last_category": "All Apps"
                    }, f, indent=2)
                    
            # Start the refresh process if this is first time or partial setup
            if needs_setup:
                # Make sure the spinner is visible before starting
                self.ensure_spinner_visible()
                
                # We need a brief delay to ensure the UI has fully initialized
                # before starting the refresh process
                GLib.timeout_add(100, lambda: self.start_refresh(is_manual=False))
                
        except Exception as e:
            print(f"Error setting up directories: {e}")
            self.show_error_dialog(f"Failed to initialize app store directories: {str(e)}")

    def check_distro_configuration(self):
        """Check and load distro configuration"""
        try:
            # Check for selected_distro file first
            distro_file = os.path.join(APPSTORE_DIR, "selected_distro")
            if os.path.exists(distro_file):
                with open(distro_file, 'r') as f:
                    self.selected_distro = f.read().strip()
                    if self.selected_distro:
                        print(f"Found selected_distro: {self.selected_distro}")

            # Check for distro_add_answer file
            answer_file = os.path.join(APPSTORE_DIR, "distro_add_answer")
            if os.path.exists(answer_file):
                with open(answer_file, 'r') as f:
                    answer = f.read().strip()
                    self.distro_enabled = answer.lower() == 'y'
                    if self.distro_enabled:
                        print(f"Found distro_add_answer: {answer} -> enabled: True")
            else:
                # Silently create default file if it doesn't exist
                with open(answer_file, 'w') as f:
                    f.write('n')
                self.distro_enabled = False

        except Exception as e:
            print(f"Error checking distro configuration: {e}")
            self.distro_enabled = False
            self.selected_distro = None

    def check_for_updates(self):
        """Check for app updates when the application starts"""
        # Make sure we have connectivity (but don't show the dialog)
        if not self.check_internet_connection():
            print("No internet connection detected during initial check, skipping auto-refresh")
            return

        try:
            # Load installed apps first to have them available
            self.load_installed_apps()
            
            # Check if auto-refresh is enabled
            auto_refresh = self.get_setting("enable_auto_refresh", True)
            if not auto_refresh:
                print("Auto-refresh is disabled, skipping")
                return
                
            # Check when the last refresh was performed
            refresh_interval = 24 * 60 * 60  # 24 hours in seconds
            if os.path.exists(LAST_VERSION_CHECK_FILE):
                try:
                    with open(LAST_VERSION_CHECK_FILE, 'r') as f:
                        last_check = float(f.read().strip())
                    
                    now = datetime.now().timestamp()
                    time_since_last_check = now - last_check
                    
                    if time_since_last_check < refresh_interval:
                        print(f"Last check was {time_since_last_check:.2f} seconds ago, skipping auto-refresh")
                        
                        # Just load metadata and set up UI
                        self.load_app_metadata_and_setup_ui()
                        
                        # Make sure search box stays hidden
                        GLib.timeout_add(500, self._ensure_search_box_hidden)
                        return
                    else:
                        print(f"Last check was {time_since_last_check:.2f} seconds ago, performing auto-refresh")
                except Exception as e:
                    print(f"Error reading last check time: {e}, performing auto-refresh")
            else:
                print("No last check time found, performing initial auto-refresh")
        
            # Perform auto-refresh
            print("Starting automatic refresh in background")
            self.start_refresh(is_manual=False)
            
            # Make sure search box stays hidden
            GLib.timeout_add(500, self._ensure_search_box_hidden)
        except Exception as e:
            print(f"Error during update check: {e}")
            
            # Even on error, try to load metadata and set up UI
            self.load_app_metadata_and_setup_ui()
            
            # Make sure search box stays hidden
            GLib.timeout_add(500, self._ensure_search_box_hidden)

    def update_app_versions(self):
        """Update versions for all apps in the background"""
        try:
            # Step 1: Load old apps.json data before backing up
            old_json_path = os.path.join(APPSTORE_OLD_JSON_DIR, 'apps.json')
            old_apps_data = []
            if os.path.exists(old_json_path):
                with open(old_json_path, 'r') as f:
                    old_apps_data = json.load(f)
                    print("Loaded old apps data")

            # Step 2: Load current apps.json data
            current_apps_data = []
            if os.path.exists(APPSTORE_JSON):
                with open(APPSTORE_JSON, 'r') as f:
                    current_apps_data = json.load(f)
                    print("Loaded current apps data")
                    
            # Check Termux Desktop configuration first
            termux_desktop_config = "/data/data/com.termux/files/usr/etc/termux-desktop/configuration.conf"
            # distro_enabled = False
            # selected_distro = None
            
            if os.path.exists(termux_desktop_config):
                try:
                    with open(termux_desktop_config, 'r') as f:
                        for line in f:
                            print(f"Raw line: '{line.strip()}'")  # Debugging output
                            if line.startswith('distro_add_answer='):
                                # Handle both quoted and unquoted values
                                value = line.strip().split('=')[1].strip().strip('"').strip("'")
                                print(f"Parsed distro_add_answer: '{value}'")  # Debugging output
                                # Set distro_enabled based on the value
                                if value.lower() in ['y', 'yes']:
                                    distro_enabled = True
                                elif value.lower() in ['n', 'no']:
                                    distro_enabled = False
                                else:
                                    print(f"Warning: Unrecognized value for distro_add_answer: '{value}'")
                                    distro_enabled = False  # Default to False if unrecognized
                            elif line.startswith('selected_distro='):
                                # Handle both quoted and unquoted values
                                selected_distro = line.strip().split('=')[1].strip().strip('"').strip("'").lower()
                                print(f"Parsed selected_distro: '{selected_distro}'")  # Debugging output
                except Exception as e:
                    print(f"Error reading Termux Desktop config: {e}")
                    return  # Exit the method if there's an error
            else:
                print("Warning: Termux Desktop not installed")

            # Step 3: Get actual versions for native apps
            for app in current_apps_data:
                if (app['app_type'] == 'native' and 
                    app.get('version') == 'termux_local_version' and 
                    app.get('package_name')):
                    cmd = f"source /data/data/com.termux/files/usr/bin/termux-setup-package-manager && "
                    cmd += f"if [[ \"$TERMUX_APP_PACKAGE_MANAGER\" == \"apt\" ]]; then "
                    cmd += f"apt-cache policy {app['package_name']} | grep 'Candidate:' | awk '{{print $2}}'; "
                    cmd += f"elif [[ \"$TERMUX_APP_PACKAGE_MANAGER\" == \"pacman\" ]]; then "
                    cmd += f"pacman -Si {app['package_name']} 2>/dev/null | grep 'Version' | awk '{{print $3}}'; fi"
                    
                    try:
                        result = subprocess.run(['bash', '-c', cmd], 
                                             capture_output=True, 
                                             text=True, 
                                             timeout=10)
                        if result.returncode == 0 and result.stdout.strip():
                            app['version'] = result.stdout.strip()
                            print(f"Got version for {app['app_name']}: {app['version']}")
                    except Exception as e:
                        print(f"Error getting version for {app['app_name']}: {e}")

            # Step 4: Get actual versions for distro apps if distro is enabled
            if distro_enabled and selected_distro:
                # First check if proot-distro is working correctly
                test_cmd = f"proot-distro login {selected_distro} --shared-tmp -- /bin/bash -c 'echo test'"
                try:
                    test_result = subprocess.run(['bash', '-c', test_cmd],
                                              capture_output=True,
                                              text=True,
                                              timeout=10)
                    if test_result.returncode != 0:
                        print(f"Error: proot-distro test failed for {selected_distro}")
                        print(f"Stderr: {test_result.stderr}")
                        return
                except Exception as e:
                    print(f"Error testing proot-distro: {e}")
                    return

                # Process all distro apps
                for app in current_apps_data:
                    if (app.get('app_type') == 'distro' and 
                        app.get('version') == 'distro_local_version'):
                        
                        supported_distro = app.get('supported_distro')
                        if supported_distro and supported_distro != 'all':
                            supported_distros = [d.strip().lower() for d in supported_distro.split(',')]
                            if selected_distro not in supported_distros:
                                print(f"Skipping {app['app_name']}: not compatible with {selected_distro}")
                                continue

                        package_name = app.get(f"{selected_distro}_run_cmd")
                        if not package_name:
                            package_name = app.get('run_cmd')
                            if package_name:
                                package_name = package_name.split()[0]
                        
                        if not package_name:
                            package_name = app.get('package_name')

                        if not package_name:
                            print(f"Skipping {app['app_name']}: no package name or run command found")
                            continue

                        print(f"Checking version for {app['app_name']} using package name: {package_name}...")
                        cmd = f"proot-distro login {selected_distro} --shared-tmp -- /bin/bash -c "
                        
                        if selected_distro in ['ubuntu', 'debian']:
                            cmd += f"'latest_version=$(apt-cache policy {package_name} | grep Candidate: | awk \"{{print \\$2}}\") && echo \"$latest_version\"'"
                        elif selected_distro == 'fedora':
                            cmd += f"'latest_version=$(dnf info {package_name} 2>/dev/null | awk -F: \"/Version/ {{print \\$2}}\" | tr -d \" \") && echo \"$latest_version\"'"
                        elif selected_distro == 'archlinux':
                            cmd += f"'latest_version=$(pacman -Si {package_name} 2>/dev/null | grep Version | awk \"{{print \\$3}}\") && echo \"$latest_version\"'"

                        try:
                            result = subprocess.run(['bash', '-c', cmd], 
                                                 capture_output=True, 
                                                 text=True, 
                                                 timeout=30)
                            if result.returncode == 0 and result.stdout.strip():
                                app['version'] = result.stdout.strip()
                                print(f"Got version for distro app {app['app_name']}: {app['version']}")
                            else:
                                print(f"Failed to get version for {app['app_name']}")
                                if result.stderr:
                                    print(f"Error: {result.stderr}")
                        except Exception as e:
                            print(f"Error getting version for distro app {app['app_name']}: {e}")
                            continue

            # Step 5: Save updated versions to new apps.json
            with open(APPSTORE_JSON, 'w') as f:
                json.dump(current_apps_data, f, indent=2)
                print("Saved updated versions to apps.json")

            # Step 6: Compare versions and update pending_updates
            for app in current_apps_data:
                if app['folder_name'] in self.installed_apps:  # Only check installed apps
                    old_app = next((a for a in old_apps_data if a['folder_name'] == app['folder_name']), None)
                    if old_app:
                        old_version = old_app.get('version')
                        new_version = app.get('version')
                        if old_version and new_version and old_version != new_version:
                            print(f"Update found for {app['app_name']}: {old_version} -> {new_version}")
                            self.pending_updates[app['folder_name']] = new_version

            # Step 7: Save pending updates
            self.save_pending_updates()
            print("Saved pending updates")

            # Refresh the UI to show updated versions
            # Get current category before refreshing
            current_category = self._get_selected_category()
            GLib.idle_add(lambda cat=current_category: self.show_apps(cat))

        except Exception as e:
            print(f"Error updating app versions: {e}")
            import traceback
            traceback.print_exc()

    def load_app_metadata_and_setup_ui(self):
        """Load app metadata and set up UI in the background"""
        self.load_app_metadata()
        GLib.idle_add(self.setup_app_list_ui)
        GLib.idle_add(self.hide_loading_indicators)  # Add this line to hide both spinner and label

    def hide_loading_indicators(self):
        """Hide all loading indicators"""
        self.spinner.stop()
        # Switch back to content view
        if hasattr(self, 'main_stack'):
            self.main_stack.set_visible_child_name("content")
        # Process events to ensure UI updates
        while Gtk.events_pending():
            Gtk.main_iteration()

    def start_refresh(self, is_manual=True, skip_connectivity_check=False):
        """Start the refresh process in a background thread"""
        # Check if a refresh operation is already in progress
        if self.is_refreshing:
            print("Refresh already in progress, skipping this request")
            return

        print("\nStarting refresh process...")
        
        # Check for internet connectivity first (unless explicitly skipped)
        if not skip_connectivity_check and not self.check_internet_connection():
            print("No internet connection available, showing prompt")
            
            # Always immediately hide spinner and loading label
            self.spinner.stop()
            
            # Force process events to ensure UI updates
            while Gtk.events_pending():
                Gtk.main_iteration()
            
            # Only show connectivity dialog if none is currently active
            if not self.connectivity_dialog_active:
                self.show_connectivity_dialog()
            return
            
        # Set the refresh flag
        self.is_refreshing = True
        
        # Store is_manual flag as instance variable
        self.is_manual_refresh = is_manual
        
        # Clear existing content
        for child in self.content_box.get_children():
            child.destroy()

        # Only hide the tab buttons, keep the header bar visible for window controls
        if hasattr(self, 'header_tabs_box'):
            self.header_tabs_box.hide()
        
        # Show the spinner page instead of content
        self.main_stack.set_visible_child_name("spinner")
        
        # Start the spinner
        self.spinner.start()
        
        # Process pending events to ensure UI updates
        while Gtk.events_pending():
            Gtk.main_iteration()

        # Start background thread for downloading
        thread = threading.Thread(target=self.refresh_data_background)
        thread.daemon = True
        thread.start()
        
    def show_connectivity_dialog(self):
        """Show a dialog with retry and cancel options when no internet connection is available"""
        # Check if a dialog is already active to prevent duplicates
        if self.connectivity_dialog_active:
            print("Connectivity dialog already active, skipping duplicate")
            return
            
        # Set the flag to indicate a dialog is active
        self.connectivity_dialog_active = True
        
        # First make sure any previous spinner is stopped
        self.spinner.stop()
        
        # Switch back to content view (from spinner view, if active)
        self.main_stack.set_visible_child_name("content")
        
        # Only hide tab buttons, but keep header bar visible for window controls
        if hasattr(self, 'header_tabs_box'):
            self.header_tabs_box.hide()
        
        # Process events to ensure UI updates immediately
        while Gtk.events_pending():
            Gtk.main_iteration()
        
        # Create the dialog with two buttons
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.WARNING,
            flags=Gtk.DialogFlags.MODAL,  # Make it modal to block other interactions
            buttons=Gtk.ButtonsType.NONE,
            text="No Internet Connection"
        )
        dialog.format_secondary_text("Please check your internet connection and try again.")
        
        # Add custom buttons
        retry_button = dialog.add_button("Retry", Gtk.ResponseType.YES)
        close_app_button = dialog.add_button("Close App", Gtk.ResponseType.CLOSE)
        
        # Style the buttons
        retry_button_context = retry_button.get_style_context()
        retry_button_context.add_class("suggested-action")
        
        # Add dialog styling
        dialog_context = dialog.get_style_context()
        dialog_context.add_class("connectivity-dialog")
        
        # The response handler that will be called when buttons are clicked
        def on_response(dialog, response_id):
            # First hide the dialog to make it visually disappear immediately
            dialog.hide()
            
            # Process events to ensure dialog is visually hidden
            while Gtk.events_pending():
                Gtk.main_iteration()
                
            # Then destroy it
            dialog.destroy()
            
            # Process events again to ensure dialog is fully destroyed
            while Gtk.events_pending():
                Gtk.main_iteration()
                
            # Reset the dialog active flag
            self.connectivity_dialog_active = False
            
            # Now handle the response
            if response_id == Gtk.ResponseType.YES:
                # User clicked Retry - check internet connection in the main loop
                def check_internet_and_refresh():
                    # Make sure spinner is still hidden during check
                    self.spinner.stop()
                    self.spinner.hide()
                    self.loading_label.hide()
                    
                    # Process events to ensure spinner is hidden
                    while Gtk.events_pending():
                        Gtk.main_iteration()
                    
                    # Check for internet connection
                    print("Retry clicked, checking internet connection")
                    has_internet = self.check_internet_connection()
                    
                    if has_internet:
                        # Internet is available
                        print("Internet connection available, starting refresh process")
                        
                        # Show spinner immediately - do this before start_refresh to ensure it's visible
                        self.spinner.set_property("visible", True)
                        self.spinner.set_property("active", True)
                        self.spinner.show_all()
                        self.spinner.start()
                        self.loading_label.set_property("visible", True)
                        self.loading_label.show_all()
                        
                        # Force UI update to show spinner
                        while Gtk.events_pending():
                            Gtk.main_iteration()
                            
                        # Start the refresh process with special flag to skip connectivity check
                        self.start_refresh(skip_connectivity_check=True)
                    else:
                        # Still no internet - make absolutely sure spinner is hidden
                        self.spinner.stop()
                        self.spinner.hide()
                        self.loading_label.hide()
                        
                        # Force update UI
                        while Gtk.events_pending():
                            Gtk.main_iteration()
                        
                        print("Still no internet connection, showing dialog again")
                        # Show the dialog again
                        self.show_connectivity_dialog()
                    
                    # Remove this function from idle queue
                    return False
                
                # Schedule the internet check function to run on the main loop
                # This ensures the dialog is fully gone before checking internet
                GLib.idle_add(check_internet_and_refresh)
                
            elif response_id == Gtk.ResponseType.CLOSE:
                # User clicked Close App - exit the application
                def quit_app():
                    print("Close App clicked, shutting down application")
                    # First destroy this window
                    self.destroy()
                    
                    # Then ensure the application quits completely
                    if self.get_application():
                        self.get_application().quit()
                    else:
                        # Fallback if application reference is not available
                        Gtk.main_quit()
                        # Additional safety - exit process
                        import sys
                        sys.exit(0)
                    return False
                
                GLib.idle_add(quit_app)
        
        # Connect the response signal to our handler
        dialog.connect("response", on_response)
        
        # Show the dialog
        dialog.show_all()

    def check_native_package_installed(self, package_name):
        """Check if a native package is installed based on package manager"""
        try:
            # Get package manager type
            cmd = "source /data/data/com.termux/files/usr/bin/termux-setup-package-manager && echo $TERMUX_APP_PACKAGE_MANAGER"
            result = subprocess.run(['bash', '-c', cmd], capture_output=True, text=True)
            pkg_manager = result.stdout.strip()

            if pkg_manager == "apt":
                # Try dpkg -l first
                cmd = f"dpkg -l | grep -q '^ii  {package_name}'"
                if subprocess.run(['bash', '-c', cmd], capture_output=True).returncode == 0:
                    return True
                
                # Try apt list as fallback
                cmd = f"apt list --installed 2>/dev/null | grep -q '^{package_name}/'"
                return subprocess.run(['bash', '-c', cmd], capture_output=True).returncode == 0
            
            elif pkg_manager == "pacman":
                # Try pacman -Qi first
                cmd = f"pacman -Qi {package_name} 2>/dev/null"
                if subprocess.run(['bash', '-c', cmd], capture_output=True).returncode == 0:
                    return True
                
                # Try pacman -Q as fallback
                cmd = f"pacman -Q {package_name} 2>/dev/null"
                return subprocess.run(['bash', '-c', cmd], capture_output=True).returncode == 0
            
            return False
        except Exception as e:
            print(f"Error checking package installation status: {e}")
            return False

    def check_distro_package_installed(self, package_name, selected_distro):
        """Check if a package is installed in the selected distro"""
        try:
            # Build command based on distro type
            cmd = f"proot-distro login {selected_distro} --shared-tmp -- /bin/bash -c "
            
            if selected_distro in ['ubuntu', 'debian']:
                # Try dpkg -l first
                cmd += f"'dpkg -l | grep -q \"^ii  {package_name}\" || "
                # Try apt list as fallback
                cmd += f"apt list --installed 2>/dev/null | grep -q \"^{package_name}/\"'"
            elif selected_distro == 'fedora':
                cmd += f"'rpm -q {package_name} >/dev/null 2>&1'"
            elif selected_distro == 'archlinux':
                # Try pacman -Qi first
                cmd += f"'pacman -Qi {package_name} >/dev/null 2>&1 || "
                # Try pacman -Q as fallback
                cmd += f"pacman -Q {package_name} >/dev/null 2>&1'"
            
            result = subprocess.run(['bash', '-c', cmd], capture_output=True)
            return result.returncode == 0
            
        except Exception as e:
            print(f"Error checking distro package installation status: {e}")
            return False

    def download_and_extract_logos(self):
        """Download and extract logos zip file"""
        try:
            # Create temp directory if it doesn't exist
            os.makedirs(TERMUX_TMP, exist_ok=True)
            
            # Download logos zip file
            logos_zip = os.path.join(TERMUX_TMP, "logos.zip")
            logos_url = "https://github.com/sabamdarif/Termux-AppStore/releases/download/logos/logos.zip"
            
            print("Downloading logos archive...")
            
            # Try to download using available download tools
            download_success = False
            
            # Try aria2c first (most efficient)
            try:
                print("Trying aria2c...")
                command = f"aria2c -x 16 -s 16 '{logos_url}' -d '{TERMUX_TMP}' -o 'logos.zip'"
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    download_success = True
                    print("Download with aria2c successful")
                else:
                    print(f"aria2c failed: {result.stderr}")
            except Exception as e:
                print(f"Error using aria2c: {e}")
            
            # Try wget if aria2c failed
            if not download_success:
                try:
                    print("Trying wget...")
                    command = f"wget '{logos_url}' -O '{logos_zip}'"
                    result = subprocess.run(command, shell=True, capture_output=True, text=True)
                    if result.returncode == 0:
                        download_success = True
                        print("Download with wget successful")
                    else:
                        print(f"wget failed: {result.stderr}")
                except Exception as e:
                    print(f"Error using wget: {e}")
            
            # Try curl if wget failed
            if not download_success:
                try:
                    print("Trying curl...")
                    command = f"curl -L '{logos_url}' -o '{logos_zip}'"
                    result = subprocess.run(command, shell=True, capture_output=True, text=True)
                    if result.returncode == 0:
                        download_success = True
                        print("Download with curl successful")
                    else:
                        print(f"curl failed: {result.stderr}")
                except Exception as e:
                    print(f"Error using curl: {e}")
            
            # Check if any download method succeeded
            if not download_success:
                print("All download methods failed")
                # Check if the directory already exists and has some content
                if os.path.exists(APPSTORE_LOGO_DIR) and os.listdir(APPSTORE_LOGO_DIR):
                    print("Using existing logo directory since download failed")
                    return True
                return False
            
            # Create logo directory
            os.makedirs(APPSTORE_LOGO_DIR, exist_ok=True)
            
            # Extract logos
            print("Extracting logos...")
            try:
                command = f"unzip -o '{logos_zip}' -d '{APPSTORE_LOGO_DIR}'"
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                
                # Clean up zip file
                if os.path.exists(logos_zip):
                    os.remove(logos_zip)
                
                # If extraction fails but directory exists with content, consider it a success
                if result.returncode != 0 and os.path.exists(APPSTORE_LOGO_DIR) and os.listdir(APPSTORE_LOGO_DIR):
                    print("Using existing logo directory since extraction failed")
                    return True
                    
                return result.returncode == 0
            except Exception as e:
                print(f"Error extracting logos: {e}")
                # If extraction fails but directory exists with content, consider it a success
                if os.path.exists(APPSTORE_LOGO_DIR) and os.listdir(APPSTORE_LOGO_DIR):
                    print("Using existing logo directory since extraction failed")
                    return True
                return False
            
        except Exception as e:
            print(f"Error handling logos: {e}")
            # Check if the directory already exists and has some content
            if os.path.exists(APPSTORE_LOGO_DIR) and os.listdir(APPSTORE_LOGO_DIR):
                print("Using existing logo directory since an error occurred")
                return True
            return False

    def refresh_data_background(self):
        try:
            print("\nStarting refresh process...")
            
            # Double-check that we're not already refreshing
            if not self.is_refreshing:
                print("Warning: Refresh flag not set, but refresh_data_background was called")
                self.is_refreshing = True
            
            # Ensure spinner is visible
            self.ensure_spinner_visible()
            
            # 1. First ensure old_json directory exists
            os.makedirs(APPSTORE_OLD_JSON_DIR, exist_ok=True)
            old_json_path = os.path.join(APPSTORE_OLD_JSON_DIR, 'apps.json')
            
            # 2. If current apps.json exists, back it up before deleting
            if os.path.exists(APPSTORE_JSON):
                print("Backing up current apps.json...")
                shutil.copy2(APPSTORE_JSON, old_json_path)
                os.remove(APPSTORE_JSON)
            
            # 3. Download new apps.json
            print("Downloading new apps.json...")
            command = f"aria2c -x 16 -s 16 {GITHUB_APPS_JSON} -d {APPSTORE_DIR} -o apps.json"
            result = os.system(command)
            if result != 0:
                print("Error downloading apps.json")
                GLib.idle_add(self.refresh_error, "Failed to download apps.json")
                return False

            # 4. Handle logos - delete existing, download and extract new
            if os.path.exists(APPSTORE_LOGO_DIR):
                print("Removing existing logos...")
                shutil.rmtree(APPSTORE_LOGO_DIR)
            
            print("Downloading and extracting new logos...")
            if not self.download_and_extract_logos():
                print("Error handling logos")
                GLib.idle_add(self.refresh_error, "Failed to update logos")
                return False

            # 5. Filter apps based on architecture compatibility
            print("Filtering apps based on architecture...")
            with open(APPSTORE_JSON, 'r') as f:
                all_apps = json.load(f)

            compatible_archs = self.arch_compatibility.get(self.system_arch, [self.system_arch])
            filtered_apps = []
            for app in all_apps:
                app_arch = app.get('supported_arch', '')
                if not app_arch:  # If no architecture specified, assume compatible
                    filtered_apps.append(app)
                    continue
                    
                supported_archs = [arch.strip().lower() for arch in app_arch.split(',')]
                
                # Check if any of the app's architectures are compatible
                if any(arch in compatible_archs for arch in supported_archs):
                    filtered_apps.append(app)
                    print(f"Added compatible app: {app['app_name']} ({app_arch})")
                else:
                    print(f"Skipped incompatible app: {app['app_name']} ({app_arch})")

            # 6. Check installed packages and update versions
            print("Checking installed packages and versions...")
            # Check Termux Desktop configuration
            termux_desktop_config = "/data/data/com.termux/files/usr/etc/termux-desktop/configuration.conf"
            distro_enabled = False  # Initialize the variable
            selected_distro = None  # Initialize the variable
            
            if os.path.exists(termux_desktop_config):
                try:
                    with open(termux_desktop_config, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('distro_add_answer='):
                                value = line.split('=')[1].strip().strip('"').strip("'").lower()  # Remove quotes
                                if value in ['y', 'yes']:
                                    distro_enabled = True
                                elif value in ['n', 'no']:
                                    distro_enabled = False
                                else:
                                    print(f"Warning: Unrecognized value for distro_add_answer: '{value}'")
                                print(f"Found distro_add_answer: {value} -> enabled: {distro_enabled}")
                            elif line.startswith('selected_distro='):
                                selected_distro = line.split('=')[1].strip().strip('"').strip("'").lower()  # Remove quotes
                                print(f"Found selected_distro: {selected_distro}")
                except Exception as e:
                    print(f"Error reading Termux Desktop config: {e}")
                    return  # Exit the method if there's an error
            else:
                print("Warning: Termux Desktop not installed")

            # Load current installed apps
            installed_apps = set()
            if os.path.exists(self.installed_apps_file):
                with open(self.installed_apps_file) as f:
                    installed_apps = set(json.load(f))

            # Check native packages and update versions
            for app in filtered_apps:
                if app['app_type'] == 'native':
                    package_name = app.get('package_name') or app.get('run_cmd')
                    if package_name:
                        if self.check_native_package_installed(package_name):
                            print(f"Found installed native package: {package_name}")
                            installed_apps.add(app['folder_name'])
                        
                        if app.get('version') == 'termux_local_version':
                            cmd = f"source /data/data/com.termux/files/usr/bin/termux-setup-package-manager && "
                            cmd += f"if [[ \"$TERMUX_APP_PACKAGE_MANAGER\" == \"apt\" ]]; then "
                            cmd += f"apt-cache policy {package_name} | grep 'Candidate:' | awk '{{print $2}}'; "
                            cmd += f"elif [[ \"$TERMUX_APP_PACKAGE_MANAGER\" == \"pacman\" ]]; then "
                            cmd += f"pacman -Si {package_name} 2>/dev/null | grep 'Version' | awk '{{print $3}}'; fi"
                            
                            try:
                                result = subprocess.run(['bash', '-c', cmd], 
                                                     capture_output=True, 
                                                     text=True, 
                                                     timeout=10)
                                if result.returncode == 0 and result.stdout.strip():
                                    app['version'] = result.stdout.strip()
                                    print(f"Updated version for {app['app_name']}: {app['version']}")
                            except Exception as e:
                                print(f"Error getting version for {app['app_name']}: {e}")

            # Check distro packages if distro is enabled
            if distro_enabled and selected_distro:
                test_cmd = f"proot-distro login {selected_distro} --shared-tmp -- /bin/bash -c 'echo test'"
                try:
                    test_result = subprocess.run(['bash', '-c', test_cmd],
                                              capture_output=True,
                                              text=True,
                                              timeout=10)
                    if test_result.returncode == 0:
                        print(f"Checking installed packages for distro: {selected_distro}")
                        
                        for app in filtered_apps:
                            if app['app_type'] == 'distro' and distro_enabled and selected_distro:
                                # Add the check for distro apps
                                supported_distro = app.get('supported_distro')
                                if supported_distro and supported_distro != 'all':
                                    # Split supported_distro into a list if it contains commas
                                    supported_distros = [d.strip().lower() for d in supported_distro.split(',')]
                                    if selected_distro not in supported_distros:
                                        print(f"Skipping {app['app_name']}: not compatible with {selected_distro}")
                                        continue

                                package_name = app.get(f"{selected_distro}_package_name") or app.get('package_name')
                                if not package_name:
                                    # Try distro-specific run command as fallback
                                    run_cmd = app.get(f"{selected_distro}_run_cmd") or app.get('run_cmd')
                                    package_name = run_cmd.split()[0] if run_cmd else None

                                if not package_name:
                                    print(f"Skipping {app['app_name']}: no package name or run command found")
                                    continue

                                # Check if installed
                                if self.check_distro_package_installed(package_name, selected_distro):
                                    print(f"Found installed distro package: {package_name}")
                                    installed_apps.add(app['folder_name'])
                                # Also check by executable path if package check failed
                                elif app.get('run_cmd'):
                                    run_cmd = app.get(f"{selected_distro}_run_cmd") or app.get('run_cmd')
                                    if self.check_distro_app_installed_by_path(run_cmd, selected_distro):
                                        print(f"Found installed distro app by path: {run_cmd}")
                                        installed_apps.add(app['folder_name'])

                                # Update version if needed
                                if app.get('version') == 'distro_local_version':
                                    # Use package_name if available, otherwise fall back to run_cmd
                                    package_name = app.get('package_name') or app.get('run_cmd')
                                    if not package_name:
                                        print(f"Skipping {app['app_name']}: no package name or run command found")
                                        continue

                                    print(f"\nDebug info for {app['app_name']}:")
                                    print(f"Package name: {package_name}")
                                    # Remove any quotes from selected_distro
                                    selected_distro = selected_distro.strip('"')
                                    print(f"Selected distro: {selected_distro}")

                                    version_cmd = None
                                    if selected_distro in ['ubuntu', 'debian']:
                                        version_cmd = f"proot-distro login {selected_distro} --shared-tmp -- /bin/bash -c 'apt-cache policy {package_name} | grep Candidate: | awk \"{{print \\$2}}\" | tr -d \"\\n\"'"
                                    elif selected_distro == 'fedora':
                                        version_cmd = f"proot-distro login {selected_distro} --shared-tmp -- /bin/bash -c 'latest_version=$(dnf info {package_name} 2>/dev/null | awk -F\": \" \"/^Version/ {{print \\$2}}\" | tr -d \"\\n\") && echo \"$latest_version\"'"
                                    elif selected_distro == 'archlinux':
                                        version_cmd = f"proot-distro login {selected_distro} --shared-tmp -- /bin/bash -c 'pacman -Si {package_name} 2>/dev/null | grep Version | awk \"{{print \\$3}}\" | tr -d \"\\n\"'"

                                    if not version_cmd:
                                        print(f"Skipping {app['app_name']}: unsupported distro {selected_distro}")
                                        continue

                                    print(f"Generated command: {version_cmd}")

                                    try:
                                        print(f"Checking version for {app['app_name']}...")
                                        result = subprocess.run(['bash', '-c', version_cmd], 
                                                             capture_output=True, 
                                                             text=True, 
                                                             timeout=30)
                                        print(f"Return code: {result.returncode}")
                                        print(f"Stdout: {result.stdout}")
                                        print(f"Stderr: {result.stderr}")
                                        
                                        if result.returncode == 0 and result.stdout.strip():
                                            app['version'] = result.stdout.strip()
                                            print(f"Updated version for distro app {app['app_name']}: {app['version']}")
                                        else:
                                            print(f"Failed to get version for {app['app_name']}")
                                            if result.stderr:
                                                print(f"Error: {result.stderr}")
                                    except Exception as e:
                                        print(f"Error getting version for distro app {app['app_name']}: {e}")
                                        print(f"Exception type: {type(e)}")
                                        continue
                    else:
                        print(f"Error: proot-distro test failed for {selected_distro}")
                        print(f"Stderr: {test_result.stderr}")
                except Exception as e:
                    print(f"Error testing proot-distro: {e}")

            # Save filtered apps with updated versions
            with open(APPSTORE_JSON, 'w') as f:
                json.dump(filtered_apps, f, indent=2)

            # Save updated installed apps list
            with open(self.installed_apps_file, 'w') as f:
                json.dump(list(installed_apps), f, indent=2)
            
            self.installed_apps = list(installed_apps)

            print("Refresh completed successfully!")
            
            if not self.stop_background_tasks:
                GLib.idle_add(self.refresh_complete)

        except Exception as e:
            print(f"Error during refresh: {e}")
            import traceback
            traceback.print_exc()
            if not self.stop_background_tasks:
                GLib.idle_add(self.refresh_error, str(e))

        return False

    def _ensure_header_hidden(self):
        """Make sure only the header tabs are hidden, but keep window controls visible"""
        # Don't hide the entire header bar, just the tabs
        if hasattr(self, 'header_tabs_box'):
            self.header_tabs_box.hide()
        return False  # Don't repeat this idle callback

    def refresh_complete(self):
        """Called when background refresh is complete"""
        print("Refresh completed")
        self.is_refreshing = False
        
        # Stop the spinner
        self.spinner.stop()
        
        # Switch back to content view
        self.main_stack.set_visible_child_name("content")
        
        # Update last version check timestamp
        from datetime import datetime as dt  # Local import to avoid conflicts
        current_time = dt.now()
        with open(LAST_VERSION_CHECK_FILE, 'w') as f:
            f.write(str(current_time.timestamp()))
        print(f"Updated last version check timestamp: {current_time}")
        
        # Show header tabs box again
        if hasattr(self, 'header_tabs_box'):
            self.header_tabs_box.show()
        
        # Process events to ensure UI updates
        while Gtk.events_pending():
            Gtk.main_iteration()

        # Skip full UI rebuild if we're just handling cancellation
        if hasattr(self, 'cancellation_in_progress') and self.cancellation_in_progress:
            # Just make sure spinner is stopped and we're in content view
            # No need to rebuild the UI or switch sections during cancellation
            return False
            
        # First load app metadata
        self.load_app_metadata()
        
        # Then set up the UI (this creates self.app_list_box, etc.)
        GLib.idle_add(self.setup_app_list_ui)
        
        # No need to call hide_loading_indicators again as we've already done it above
        
        # If this was an automatic refresh, don't switch sections
        if not hasattr(self, 'is_manual_refresh') or self.is_manual_refresh:
            # Schedule section display AFTER UI is set up
            GLib.timeout_add(100, self._show_initial_section)
        
        # Make sure search box stays hidden by default after refresh
        GLib.timeout_add(200, self._ensure_search_box_hidden)
        
        # Process UI events to make sure changes take effect
        while Gtk.events_pending():
            Gtk.main_iteration()
            
        return False
        
    def _show_initial_section(self):
        """Show the initial section after refresh (with delay to ensure UI is ready)"""
        try:
            # Trigger display of the appropriate section
            if hasattr(self, 'current_section'):
                self.on_section_clicked(self.explore_button, self.current_section)
            else:
                self.on_section_clicked(self.explore_button, "explore")
        except Exception as e:
            print(f"Error showing initial section: {e}")
            import traceback
            traceback.print_exc()
        return False

    def load_installed_apps(self):
        """Load the list of installed apps"""
        try:
            if os.path.exists(self.installed_apps_file):
                with open(self.installed_apps_file) as f:
                    self.installed_apps = json.load(f)
            else:
                self.installed_apps = []
                self.save_installed_apps()
        except (FileNotFoundError, json.JSONDecodeError):
            self.installed_apps = []
            self.save_installed_apps()

    def save_installed_apps(self):
        """Save the list of installed apps"""
        with open(self.installed_apps_file, 'w') as f:
            json.dump(self.installed_apps, f, indent=2)

    def update_installation_status(self, app_name, installed):
        """Update the installation status of an app"""
        if installed and app_name not in self.installed_apps:
            self.installed_apps.append(app_name)
        elif not installed and app_name in self.installed_apps:
            self.installed_apps.remove(app_name)
        self.save_installed_apps()
        # Get current category before refreshing
        current_category = self._get_selected_category()
        GLib.idle_add(lambda cat=current_category: self.show_apps(cat))

    def is_arch_compatible(self, app_arch):
        """Check if the app's architecture is compatible with the system"""
        if not app_arch:  # If no architecture specified, assume compatible
            return True
            
        # Split multiple architectures if present
        supported_archs = [arch.strip().lower() for arch in app_arch.split(',')]
        
        # Get compatible architectures for the system
        compatible_archs = self.arch_compatibility.get(self.system_arch, [self.system_arch])
        
        # Check if any of the app's supported architectures match the system's compatible ones
        return any(arch in compatible_archs for arch in supported_archs)

    def load_app_metadata(self):
        """Load app metadata from the centralized JSON file"""
        try:
            # Show spinner and loading label during metadata loading
            GLib.idle_add(lambda: self.spinner.show())
            GLib.idle_add(lambda: self.spinner.start())
            GLib.idle_add(lambda: self.loading_label.set_text("Loading app metadata..."))
            GLib.idle_add(lambda: self.loading_label.show())
            
            # First check Termux Desktop configuration
            termux_desktop_config = "/data/data/com.termux/files/usr/etc/termux-desktop/configuration.conf"
            distro_enabled = False  # Initialize the variable
            selected_distro = None  # Initialize the variable
            
            if os.path.exists(termux_desktop_config):
                try:
                    with open(termux_desktop_config, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('#') or not line:
                                continue
                            if line.startswith('distro_add_answer='):
                                value = line.split('=')[1].strip().strip('"').strip("'").lower()  # Remove quotes
                                self.distro_add_answer = value
                                # Set distro_enabled based on the value
                                if value in ['y', 'yes']:
                                    distro_enabled = True
                                elif value in ['n', 'no']:
                                    distro_enabled = False
                                else:
                                    print(f"Warning: Unrecognized value for distro_add_answer: '{value}'")
                                print(f"Found distro_add_answer: {value} -> enabled: {distro_enabled}")
                            elif line.startswith('selected_distro='):
                                selected_distro = line.split('=')[1].strip().strip('"').strip("'").lower()  # Remove quotes
                                print(f"Found selected_distro: {selected_distro}")
                except Exception as e:
                    print(f"Error reading Termux Desktop config: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("Warning: Termux Desktop configuration file not found")

            # Set distro_enabled based on the parsed value
            if self.distro_add_answer in ["y", "yes"]:
                distro_enabled = True

            print(f"\nConfiguration status:")
            print(f"Distro enabled: {distro_enabled}")
            print(f"Selected distro: {selected_distro}")

            with open(APPSTORE_JSON) as f:
                all_apps = json.load(f)
                
            # Get compatible architectures for the system
            compatible_archs = self.arch_compatibility.get(self.system_arch, [self.system_arch])
            print(f"System architecture: {self.system_arch}")
            print(f"Compatible architectures: {compatible_archs}")
            
            # Filter apps based on architecture compatibility and distro settings
            self.apps_data = []
            for app in all_apps:
                # Check architecture compatibility first
                app_arch = app.get('supported_arch', '')
                if not app_arch:  # If no architecture specified, assume compatible
                    self.apps_data.append(app)
                    continue
                    
                # Split and clean architecture strings
                supported_archs = [arch.strip().lower() for arch in app_arch.split(',')]
                
                # Check if any of the app's architectures are compatible
                if any(arch in compatible_archs for arch in supported_archs):
                    # For native apps, add them directly
                    if app.get('app_type') != 'distro':
                        self.apps_data.append(app)
                        print(f"Added compatible app: {app['app_name']} ({app_arch})")
                        continue

                    # For distro apps, check distro compatibility
                    if not distro_enabled:
                        print(f"Skipping distro app {app['app_name']}: distro support disabled")
                        continue
                        
                    # Check distro compatibility
                    supported_distro = app.get('supported_distro')
                    if supported_distro == 'all':
                        self.apps_data.append(app)
                        print(f"Added compatible app: {app['app_name']} ({app_arch})")
                    elif supported_distro:
                        # Split supported_distro into a list if it contains commas
                        supported_distros = [d.strip().lower() for d in supported_distro.split(',')]
                        if selected_distro in supported_distros:
                            self.apps_data.append(app)
                            print(f"Added compatible app: {app['app_name']} ({app_arch})")
                        else:
                            print(f"Skipping incompatible distro app {app['app_name']}: requires one of {supported_distros}, but using {selected_distro}")
                else:
                    print(f"Skipped incompatible app: {app['app_name']} ({app_arch})")
            
            # Extract categories from filtered apps
            self.categories = sorted(list(set(
                cat for app in self.apps_data
                for cat in app['categories']
            )))
            
            print(f"Loaded {len(self.apps_data)} compatible apps out of {len(all_apps)} total apps")
            
            # Hide spinner and loading label after completion
            GLib.idle_add(lambda: self.spinner.stop())
            GLib.idle_add(lambda: self.spinner.hide())
            GLib.idle_add(lambda: self.loading_label.hide())
            
        except FileNotFoundError:
            self.apps_data = []
            self.categories = []
            print("No apps.json file found")
            GLib.idle_add(lambda: self.spinner.stop())
            GLib.idle_add(lambda: self.spinner.hide())
            GLib.idle_add(lambda: self.loading_label.hide())
        except Exception as e:
            print(f"Error loading app metadata: {e}")
            self.apps_data = []
            self.categories = []
            GLib.idle_add(lambda: self.spinner.stop())
            GLib.idle_add(lambda: self.spinner.hide())
            GLib.idle_add(lambda: self.loading_label.hide())

    def setup_app_list_ui(self):
        """Set up the main app list UI"""
        # Add architecture warning for non-arm64 systems
        if self.system_arch not in ['arm64', 'aarch64']:
            warning_bar = Gtk.InfoBar()
            warning_bar.set_message_type(Gtk.MessageType.WARNING)
            warning_bar.set_show_close_button(True)
            warning_bar.connect("response", lambda bar, resp: bar.destroy())
            
            warning_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            warning_icon = Gtk.Image.new_from_icon_name("dialog-warning", Gtk.IconSize.MENU)
            warning_box.pack_start(warning_icon, False, False, 0)
            
            warning_label = Gtk.Label()
            warning_label.set_markup(f"System architecture <b>{self.system_arch}</b> might get some compatibility issues")
            warning_box.pack_start(warning_label, False, False, 0)
            
            warning_bar.get_content_area().add(warning_box)
            self.main_box.pack_start(warning_bar, False, False, 0)
            warning_bar.show_all()

        # Left panel - Categories
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.sidebar.set_size_request(200, -1)
        self.sidebar.set_margin_start(10)
        self.sidebar.set_margin_end(10)
        self.sidebar.set_margin_top(10)
        self.sidebar.set_margin_bottom(10)  # Add bottom margin
        self.content_box.pack_start(self.sidebar, False, True, 0)
        
        # Category list
        categories_label = Gtk.Label()
        categories_label.set_markup("<b>Categories</b>")
        categories_label.set_xalign(0)
        categories_label.set_margin_start(10)
        categories_label.set_margin_top(10)
        categories_label.set_margin_bottom(10)
        self.sidebar.pack_start(categories_label, False, True, 0)
        
        # Add "All Apps" button first
        all_button = Gtk.Button(label="All Apps")
        all_button.connect("clicked", self.on_category_clicked)
        all_button.set_size_request(180, 40)  # Set fixed width and height
        all_button.get_style_context().add_class("category-button")
        all_button.get_style_context().add_class("selected")
        self.sidebar.pack_start(all_button, False, True, 0)

        # Category buttons
        self.category_buttons = [all_button]
        for category in sorted(self.categories):
            button = Gtk.Button(label=category)
            button.connect("clicked", self.on_category_clicked)
            button.set_size_request(180, 40)  # Set fixed width and height
            button.get_style_context().add_class("category-button")
            self.sidebar.pack_start(button, False, True, 0)
            self.category_buttons.append(button)

        # Right panel container
        self.right_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.content_box.pack_start(self.right_panel, True, True, 0)

        # Add search entry at the top of app list
        self.search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.search_box.set_margin_start(10)
        self.search_box.set_margin_end(10)
        self.search_box.set_margin_top(10)
        self.search_box.get_style_context().add_class('search-box')
        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Search apps...")
        self.search_entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "system-search-symbolic")
        self.search_entry.set_icon_activatable(Gtk.EntryIconPosition.PRIMARY, False)
        self.search_entry.get_style_context().add_class('search-entry')
        self.search_entry.connect("changed", self.on_search_changed)
        # Connect Enter key to trigger a focus change to the app list
        self.search_entry.connect("activate", self.on_search_entry_activate)
        self.search_entry.set_size_request(-1, 40)
        self.search_box.pack_start(self.search_entry, True, True, 0)
        self.right_panel.pack_start(self.search_box, False, True, 0)
        
        # Hide search box by default - will be shown when search button is clicked
        self.search_box.hide()
        
        # Schedule another hide call with a delay to ensure it stays hidden
        GLib.timeout_add(100, self._ensure_search_box_hidden)

        # Create check for updates button (initially hidden)
        self.update_button = Gtk.Button(label="Check for Updates")
        self.update_button.get_style_context().add_class('system-update-button')
        self.update_button.connect("clicked", self.on_update_system)
        self.update_button.set_margin_top(10)
        self.update_button.set_margin_start(10)
        self.update_button.set_margin_end(10)
        self.update_button.set_margin_bottom(10)
        self.update_button.hide()  # Initially hidden
        self.right_panel.pack_start(self.update_button, False, False, 0)

        # Scrolled window for app list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        self.right_panel.pack_start(scrolled, True, True, 0)
        
        # Connect to vadjustment value-changed signal to detect scrolling
        vadj = scrolled.get_vadjustment()
        vadj.connect("value-changed", self.on_scroll_value_changed)
        self.last_scroll_position = 0  # Track scroll position

        # App list box
        self.app_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.app_list_box.set_margin_start(10)
        self.app_list_box.set_margin_end(10)
        self.app_list_box.set_margin_top(10)
        self.app_list_box.set_margin_bottom(10)
        scrolled.add(self.app_list_box)

        # Show all apps initially with "All Apps" selected
        self.show_apps(None)  # Pass None to show all apps
        self.content_box.show_all()
        self.update_button.hide()  # Ensure update button is hidden initially

    def on_category_clicked(self, button):
        """Handle category button clicks"""
        # Update selected state of category buttons
        for child in self.category_buttons:
            child.get_style_context().remove_class('selected')
        button.get_style_context().add_class('selected')

        category = button.get_label()
        print(f"Category selected: {category}")
        
        # Hide search box when changing categories
        if hasattr(self, 'search_box') and self.search_box.get_visible():
            self.search_box.hide()
            # Update search button icon and tooltip
            if hasattr(self, 'search_button'):
                self.search_button.set_image(Gtk.Image.new_from_icon_name("system-search-symbolic", Gtk.IconSize.BUTTON))
                self.search_button.set_tooltip_text("Show Search")
        
        # Get current search text before clearing
        current_search = self.search_entry.get_text()
        
        # Only clear search if user hasn't entered anything
        if not current_search:
            self.search_entry.set_text("")
            
        # Show apps for the selected category
        self.show_apps(category)

    def on_refresh_clicked(self, button):
        """Handle refresh button click"""
        # Delete apps.json and logo folder
        if os.path.exists(APPSTORE_JSON):
            os.remove(APPSTORE_JSON)
        if os.path.exists(APPSTORE_LOGO_DIR):
            shutil.rmtree(APPSTORE_LOGO_DIR)

        # Start the refresh process
        self.start_refresh()

    def show_error_dialog(self, message):
        """Show an error dialog with the given message"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.run()
        dialog.destroy()

    def on_install_clicked(self, button, app):
        """Handle install button click"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Install {app['app_name']}?"
        )
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            # Create progress dialog with terminal toggle
            progress_dialog, status_label, progress_bar, terminal_view = self.create_progress_dialog("Installing...")
            
            # Track current process and script path
            install_process = None
            install_cancelled = False
            script_file = None
            
            # Get cancel button using the dialog's action area
            cancel_button = None
            for button in progress_dialog.get_action_area().get_children():
                if isinstance(button, Gtk.Button) and button.get_label() in ["Cancel", "_Cancel"]:
                    cancel_button = button
                    break

            def on_cancel_clicked(*args):
                nonlocal install_process, install_cancelled, progress_dialog, script_file
                install_cancelled = True
                
                # Properly terminate the process if it exists
                if install_process and install_process.poll() is None:
                    try:
                        # First try SIGTERM
                        os.killpg(os.getpgid(install_process.pid), signal.SIGTERM)
                        
                        # Wait a second for process to terminate
                        start_time = time.time()
                        while time.time() - start_time < 1 and install_process.poll() is None:
                            time.sleep(0.1)
                        
                        # If process still running, use SIGKILL
                        if install_process.poll() is None:
                            os.killpg(os.getpgid(install_process.pid), signal.SIGKILL)
                            
                        terminal_update = "Installation cancelled by user. Terminating process..."
                        GLib.idle_add(lambda: self.update_terminal(terminal_view, terminal_update))
                    except Exception as e:
                        print(f"Error terminating process: {e}")
                
                # Clean up the script file
                if script_file and os.path.exists(script_file):
                    try:
                        os.remove(script_file)
                        print(f"Cleaned up script: {script_file}")
                    except Exception as e:
                        print(f"Error removing script file: {e}")
                
                # Make sure the dialog is destroyed only once
                if progress_dialog and progress_dialog.get_visible():
                    # Set a flag to avoid multiple calls to show_apps
                    self.cancellation_in_progress = True
                    
                    # Try to disconnect the response signal using the saved handler ID
                    try:
                        nonlocal dialog_response_handler_id
                        progress_dialog.handler_disconnect(dialog_response_handler_id)
                    except Exception as e:
                        # Ignore errors if the handler can't be disconnected
                        print(f"Note: Could not disconnect dialog handler: {e}")
                    
                    # Add a small delay before destroying the dialog
                    GLib.timeout_add(500, lambda: progress_dialog.destroy() if progress_dialog and progress_dialog.get_visible() else None)
                    # Clear the flag after dialog is destroyed
                    GLib.timeout_add(600, lambda: setattr(self, 'cancellation_in_progress', False))
                
                return True

            # Connect the response signal
            progress_dialog.connect('response', on_cancel_clicked)
            
            # Find and connect the cancel button if it exists
            cancel_button = None
            
            # Try several methods to find the cancel button
            # Method 1: Check for action area buttons
            action_area = progress_dialog.get_action_area()
            if action_area:
                for button in action_area.get_children():
                    if isinstance(button, Gtk.Button) and button.get_label() in ["Cancel", "_Cancel"]:
                        cancel_button = button
                        break
            
            # Method 2: Search in content area if not found
            if cancel_button is None:
                for child in progress_dialog.get_content_area().get_children():
                    if isinstance(child, Gtk.Box):
                        for button in child.get_children():
                            if isinstance(button, Gtk.Button) and button.get_label() in ["Cancel", "_Cancel"]:
                                cancel_button = button
                                break
            
            # Connect to the button if found
            if cancel_button:
                cancel_button.connect("clicked", on_cancel_clicked)
            else:
                print("Warning: Cancel button not found in dialog")

            def on_dialog_response(dialog, response_id):
                """Handle dialog responses that might come through the window manager"""
                if response_id == Gtk.ResponseType.CANCEL or response_id == Gtk.ResponseType.DELETE_EVENT:
                    # Use the same cancel handler for consistency
                    on_cancel_clicked()
            
            # Store the handler ID for later disconnection if needed
            dialog_response_handler_id = progress_dialog.connect("response", on_dialog_response)
            
            def update_progress(fraction, status_text):
                if not status_text:
                    return False
                
                # Check if dialog is still valid
                if not progress_dialog or not progress_dialog.get_window():
                    return False
                
                # Update both progress view and terminal view
                if '[#' in status_text and ']' in status_text:
                    # Extract progress details from aria2c output
                    progress_part = status_text[status_text.find('['):status_text.find(']')+1]
                    file_part = status_text[status_text.find(']')+1:].strip()
                    
                    # Format the status text to show both progress and file
                    status_label.set_text(f"{progress_part}\n{file_part}")
                elif isinstance(status_text, str) and status_text.strip():
                    status_label.set_text(status_text)
                
                # Get the stack widget from the progress dialog
                stack = None
                try:
                    for child in progress_dialog.get_content_area().get_children():
                        if isinstance(child, Gtk.Stack):
                            stack = child
                            break
                except Exception:
                    return False
                
                # Always update terminal view
                GLib.idle_add(lambda: self.update_terminal(terminal_view, status_text))
                
                # Make sure terminal view is shown if setting is enabled
                if stack and self.get_setting("use_terminal_for_progress", False):
                    GLib.idle_add(lambda s=stack: s.set_visible_child_name("terminal"))
                
                progress_bar.set_fraction(fraction)
                progress_bar.set_text(f"{int(fraction * 100)}%")
                return False

            def install_thread():
                try:
                    # Ensure cancelled flag is synced
                    self.installation_cancelled = install_cancelled
                    
                    # Download script (20%)
                    GLib.idle_add(update_progress, 0.2, "Downloading install script...")
                    script_file = self.download_script(app['install_url'])
                    if not script_file or install_cancelled:
                        if script_file and os.path.exists(script_file):
                            os.remove(script_file)
                        GLib.idle_add(progress_dialog.destroy)
                        return

                    # Make script executable (30%)
                    GLib.idle_add(update_progress, 0.3, "Preparing installation...")
                    os.chmod(script_file, os.stat(script_file).st_mode | stat.S_IEXEC)

                    # Count the number of significant lines in the script to track progress
                    total_lines = 0
                    significant_lines = []
                    try:
                        with open(script_file, 'r') as f:
                            for line in f:
                                # Skip empty lines and comments
                                line = line.strip()
                                if line and not line.startswith('#'):
                                    total_lines += 1
                                    significant_lines.append(line)
                        # Ensure we have at least one line
                        total_lines = max(1, total_lines)
                        GLib.idle_add(lambda: self.update_terminal(terminal_view, f"Script contains {total_lines} executable steps\n"))
                        
                        # Check if script contains any download_file commands
                        # If it does, disable cancel button preemptively
                        has_download_operations = any("download_file" in line.lower() for line in significant_lines)
                        has_extract_operations = any("extract" in line.lower() for line in significant_lines)
                        
                        # If script has critical operations, disable cancel button
                        if (has_download_operations or has_extract_operations) and cancel_button and not cancel_button_disabled:
                            msg = "Installation contains critical operations and cannot be cancelled once started"
                            GLib.idle_add(lambda: self.update_terminal(terminal_view, f"\n*** {msg} ***\n"))
                            GLib.idle_add(lambda: cancel_button.set_sensitive(False))
                            GLib.idle_add(lambda: cancel_button.set_tooltip_text(msg))
                            cancel_button_disabled = True
                            
                    except Exception as e:
                        print(f"Error counting script lines: {e}")
                        # Default to a reasonable number if counting fails
                        total_lines = 100
                    
                    # Calculate base progress (downloading and preparation = 30%)
                    base_progress = 0.3
                    # Calculate line progress (each line contributes to 60% of progress)
                    line_progress_weight = 0.6 / total_lines
                    
                    # Execute script with better progress tracking
                    GLib.idle_add(update_progress, base_progress, "Starting installation...")
                    install_process = subprocess.Popen(
                        ['bash', script_file],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1,
                        preexec_fn=os.setsid  # Create new process group
                    )
                    
                    # Track current line
                    current_line = 0
                    accumulated_weight = 0.0  # Track accumulated weight of processed operations
                    cancel_button_disabled = False  # Track if cancel button is disabled
                    
                    # Forcibly disable cancel button for certain patterns known to be critical
                    if cancel_button:
                        for line in significant_lines:
                            if ("download_file" in line.lower() or 
                                "extract" in line.lower() or 
                                "check_and_delete" in line.lower() or
                                "check_and_create_directory" in line.lower() or
                                "/opt/brave-browser" in line.lower()):
                                GLib.idle_add(lambda: cancel_button.set_sensitive(False))
                                GLib.idle_add(lambda: cancel_button.set_tooltip_text("Installation is processing critical operations and cannot be cancelled"))
                                GLib.idle_add(lambda: self.update_terminal(terminal_view, "\nInstallation is processing critical operations and cannot be cancelled\n"))
                                cancel_button_disabled = True
                                break
                    
                    while True:
                        if install_cancelled:
                            try:
                                os.killpg(os.getpgid(install_process.pid), signal.SIGTERM)
                                install_process.wait(timeout=2)
                            except:
                                pass
                            GLib.idle_add(progress_dialog.destroy)
                            return

                        line = install_process.stdout.readline()
                        if not line and install_process.poll() is not None:
                            break

                        line = line.strip()
                        if not line:
                            continue
                            
                        # Check if this is a heavy operation that should disable cancel button
                        if not cancel_button_disabled and self.is_heavy_operation(line) and cancel_button:
                            GLib.idle_add(lambda: cancel_button.set_sensitive(False))
                            GLib.idle_add(lambda: cancel_button.set_tooltip_text("Installation is processing critical operations and cannot be cancelled"))
                            GLib.idle_add(lambda: self.update_terminal(terminal_view, "\nInstallation is processing critical operations and cannot be cancelled\n"))
                            cancel_button_disabled = True

                        # Update current line and calculate progress
                        current_line += 1
                        # Ensure we don't exceed our total for any reason
                        current_line = min(current_line, total_lines)
                        
                        # Calculate line weight for more accurate progress
                        line_weight = self.estimate_line_weight(line)
                        
                        # Calculate current progress
                        # Base progress + (current line / total lines) * remaining progress
                        # This still uses line count but shows slower progress for heavy operations
                        if self.is_heavy_operation(line):
                            # For heavy operations, wait for the operation to complete
                            # Start progress from current point
                            current_progress = base_progress + (current_line - 1) * line_progress_weight
                            # End progress is what it would be after this operation
                            next_progress = base_progress + current_line * line_progress_weight
                            # Cap at 90%
                            next_progress = min(0.9, next_progress)
                            
                            # Update terminal immediately
                            GLib.idle_add(lambda l=line: self.update_terminal(terminal_view, l + "\n"))
                            
                            # Special handling for download_file operations which need more progress feedback
                            if "download_file" in line.lower():
                                # Make sure we show progress immediately
                                GLib.idle_add(update_progress, current_progress, f"Downloading: {line}")
                                
                                # Create a thread to monitor download progress
                                def monitor_download_progress():
                                    steps = 100  # More steps for smoother progress during downloads
                                    step_size = (next_progress - current_progress) / steps
                                    download_duration = 15.0  # Longer duration for downloads
                                    step_time = download_duration / steps
                                    
                                    # First wait to let the download start
                                    time.sleep(0.5)
                                    
                                    # Get the file name being downloaded if possible
                                    file_name = None
                                    match = re.search(r'download_file.*"([^"]+)"', line)
                                    if match:
                                        file_name = os.path.basename(match.group(1))
                                        print(f"Monitoring download of: {file_name}")
                                    
                                    for step in range(steps):
                                        # Check if installation is cancelled
                                        if install_cancelled:
                                            return
                                        
                                        # Calculate intermediate progress
                                        intermediate_progress = current_progress + (step_size * step)
                                        
                                        # Update progress with file name if available
                                        status_text = f"Downloading{''+f': {file_name}' if file_name else ''} - {int(step/steps*100)}%"
                                        GLib.idle_add(update_progress, intermediate_progress, status_text)
                                        
                                        # Sleep for step time
                                        time.sleep(step_time)
                                        
                                        # Try to determine if download is complete
                                        # Check if the process has ended or next line processed
                                        if install_process.poll() is not None:
                                            break
                                    
                                    # Final update to show download completed
                                    GLib.idle_add(update_progress, next_progress, f"Download completed{': '+file_name if file_name else ''}")
                                
                                # Start the monitoring thread
                                download_thread = threading.Thread(target=monitor_download_progress)
                                download_thread.daemon = True
                                download_thread.start()
                                
                                # Continue with next line without updating progress again
                                continue
                            else:
                                # Gradually update progress for other heavy operations (5-8 seconds based on operation)
                                duration = self.get_operation_duration(line)
                                self.update_progress_gradually(update_progress, current_progress, next_progress, line, duration)
                            
                            # Continue with the next line without updating progress again
                            continue
                        else:
                            # For normal operations, update immediately
                            current_progress = base_progress + (current_line * line_progress_weight)
                            
                            # Cap progress at 90% - the final 10% is reserved for completion tasks
                            current_progress = min(0.9, current_progress)
                            
                            # Update progress
                            GLib.idle_add(update_progress, current_progress, line)
                            
                            # Update terminal
                            GLib.idle_add(lambda l=line: self.update_terminal(terminal_view, l + "\n"))

                    if install_process.wait() == 0 and not install_cancelled:
                        # Update installation status (95%)
                        GLib.idle_add(update_progress, 0.95, "Finalizing installation...")
                        self.update_installation_status(app['folder_name'], True)
                        
                        # Remove from pending updates if this was an update
                        if app['folder_name'] in self.pending_updates:
                            del self.pending_updates[app['folder_name']]
                            self.save_pending_updates()
                        
                        # Get current category before refreshing
                        current_category = self._get_selected_category()
                        GLib.idle_add(lambda cat=current_category: self.show_apps(cat))
                        
                        # Complete (100%)
                        GLib.idle_add(update_progress, 1.0, "Installation complete!")

                        # Close log file if logging is active
                        if self.logging_active and self.log_file:
                            try:
                                self.log_file.write("\n--- Installation completed successfully ---\n")
                                self.log_file.close()
                            except Exception:
                                pass
                            self.log_file = None
                            self.logging_active = False
                            self.log_file_path = None

                        # Delay closing the dialog a bit to show the completion message
                        time.sleep(2)
                    else:
                        if not install_cancelled:  # Only show error if not cancelled
                            GLib.idle_add(update_progress, 1.0, "Installation failed!")
                            
                            # Close log file if logging is active
                            if self.logging_active and self.log_file:
                                try:
                                    self.log_file.write("\n--- Installation failed ---\n")
                                    self.log_file.close()
                                except Exception:
                                    pass
                                self.log_file = None
                                self.logging_active = False
                                self.log_file_path = None
                                
                            time.sleep(2)
                    
                    # Clean up and close dialog
                    GLib.idle_add(progress_dialog.destroy)
                    if script_file and os.path.exists(script_file):
                        try:
                            os.remove(script_file)
                        except:
                            pass

                except Exception as e:
                    print(f"Installation error: {str(e)}")
                    GLib.idle_add(update_progress, 1.0, f"Error: {str(e)}")
                    
                    # Close log file if logging is active
                    if self.logging_active and self.log_file:
                        try:
                            self.log_file.write(f"\n--- Installation error: {str(e)} ---\n")
                            self.log_file.close()
                        except Exception:
                            pass
                        self.log_file = None
                        self.logging_active = False
                        self.log_file_path = None
                    
                    time.sleep(2)
                    GLib.idle_add(progress_dialog.destroy)
                
                finally:
                    if install_process:
                        try:
                            os.killpg(os.getpgid(install_process.pid), signal.SIGTERM)
                        except:
                            pass
                    install_process = None
                    if script_file and os.path.exists(script_file):
                        try:
                            os.remove(script_file)
                            print(f"Cleaned up script: {script_file}")
                        except Exception as e:
                            print(f"Error cleaning up script: {e}")

            thread = threading.Thread(target=install_thread)
            thread.daemon = True
            thread.start()

    def modify_script(self, script_path):
        """Add source line for common functions after shebang"""
        try:
            # Read the original script content
            with open(script_path, 'r') as f:
                content = f.read()
            
            # Get path to inbuild_functions
            inbuild_functions_path = Path(__file__).parent / 'inbuild_functions' / 'inbuild_functions'
            
            # Add inbuild_functions source after shebang
            # Try both common shebang variants
            for shebang in ['#!/data/data/com.termux/files/usr/bin/bash\n', '#!/bin/bash\n']:
                if shebang in content:
                    new_content = content.replace(
                        shebang,
                        f'{shebang}source {inbuild_functions_path}\n'
                    )
                    
                    # Write modified content back
                    with open(script_path, 'w') as f:
                        f.write(new_content)
                    return True
            
            print("No compatible shebang found in script")
            return False
                
        except Exception as e:
            print(f"Error injecting common_functions source: {e}")
            return False

    def download_script(self, url):
        """Download a script from URL and return its local path"""
        try:
            # Create temp directory if it doesn't exist
            os.makedirs(TERMUX_TMP, exist_ok=True)

            # Create a temporary file
            script_name = f"appstore_{int(time.time())}.sh"
            script_path = os.path.join(TERMUX_TMP, script_name)

            # Download using aria2c with proper encoding handling
            print(f"Downloading script from {url} to {script_path}")
            command = f"aria2c -x 16 -s 16 '{url}' -d '{TERMUX_TMP}' -o '{script_name}'"
            result = subprocess.run(command, shell=True, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode != 0:
                print(f"Download failed: {result.stderr}")
                return None

            # Verify file exists and is readable
            if not os.path.exists(script_path):
                print("Script file not found after download")
                return None

            # Read file content to verify encoding
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                print("Script file has invalid encoding")
                if os.path.exists(script_path):
                    os.remove(script_path)
                return None

            # Modify script to source common functions
            if not self.modify_script(script_path):
                print("Failed to modify script")
                return None

            return script_path
        except Exception as e:
            print(f"Error downloading script: {e}")
            if script_path and os.path.exists(script_path):
                os.remove(script_path)
            return None

    def on_uninstall_clicked(self, button, app):
        """Handle uninstall button click"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Uninstall {app['app_name']}?"
        )
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            # Create progress dialog with terminal functionality
            progress_dialog, status_label, progress_bar, terminal_view = self.create_progress_dialog(
                title="Uninstalling...",
                allow_cancel=True
            )
            
            # Initialize variables for nonlocal access
            uninstall_process = None
            uninstall_cancelled = False
            script_file = None
            
            # Get cancel button using the dialog's action area
            cancel_button = None
            for button in progress_dialog.get_action_area().get_children():
                if isinstance(button, Gtk.Button) and button.get_label() in ["Cancel", "_Cancel"]:
                    cancel_button = button
                    break

            def on_cancel_clicked(*args):
                nonlocal uninstall_process, uninstall_cancelled, progress_dialog, script_file
                uninstall_cancelled = True
                
                # Properly terminate the process if it exists
                if uninstall_process and uninstall_process.poll() is None:
                    try:
                        # First try SIGTERM
                        os.killpg(os.getpgid(uninstall_process.pid), signal.SIGTERM)
                        
                        # Wait a second for process to terminate
                        start_time = time.time()
                        while time.time() - start_time < 1 and uninstall_process.poll() is None:
                            time.sleep(0.1)
                        
                        # If process still running, use SIGKILL
                        if uninstall_process.poll() is None:
                            os.killpg(os.getpgid(uninstall_process.pid), signal.SIGKILL)
                            
                        terminal_update = "Uninstallation cancelled by user. Terminating process..."
                        GLib.idle_add(lambda: self.update_terminal(terminal_view, terminal_update))
                    except Exception as e:
                        print(f"Error terminating process: {e}")
                    
                # Clean up the script file
                if script_file and os.path.exists(script_file):
                    try:
                        os.remove(script_file)
                        print(f"Cleaned up script: {script_file}")
                    except Exception as e:
                        print(f"Error removing script file: {e}")
                    
                # Make sure the dialog is destroyed only once
                if progress_dialog and progress_dialog.get_visible():
                    # Set a flag to avoid multiple calls to show_apps
                    self.cancellation_in_progress = True
                    
                    # Add a small delay before destroying the dialog
                    GLib.timeout_add(500, lambda: progress_dialog.destroy() if progress_dialog and progress_dialog.get_visible() else None)
                    # Clear the flag after dialog is destroyed
                    GLib.timeout_add(600, lambda: setattr(self, 'cancellation_in_progress', False))
                
                return True

            def update_progress(fraction, status_text):
                # Check if dialog is still valid before proceeding
                if not progress_dialog or not progress_dialog.get_window():
                    return False
                
                if status_text and not status_text.strip('-'):
                    status_label.set_text(status_text)
                    self.update_terminal(terminal_view, status_text + "\n")
                
                # Get the stack widget from the progress dialog
                stack = None
                try:
                    for child in progress_dialog.get_content_area().get_children():
                        if isinstance(child, Gtk.Stack):
                            stack = child
                            break
                except Exception as e:
                    # Dialog may have been destroyed during processing
                    print(f"Error accessing dialog content: {e}")
                    return False
                
                # Make sure terminal view is shown if setting is enabled
                if stack and self.get_setting("use_terminal_for_progress", False):
                    GLib.idle_add(lambda s=stack: s.set_visible_child_name("terminal"))
                
                progress_bar.set_fraction(fraction)
                progress_bar.set_text(f"{int(fraction * 100)}%")
                return False

            def uninstall_thread():
                nonlocal script_file, uninstall_process
                try:
                    # Check if uninstall script URL is available
                    uninstall_url = app.get('uninstall_url') or app.get('uninstall_script')
                    if not uninstall_url:
                        error_msg = "No uninstall script available for this app!"
                        GLib.idle_add(update_progress, 1.0, error_msg)
                        GLib.idle_add(lambda: self.update_terminal(terminal_view, error_msg + "\n"))
                        time.sleep(2)
                        GLib.idle_add(progress_dialog.destroy)
                        return

                    # Download uninstall script
                    GLib.idle_add(update_progress, 0.1, "Downloading uninstall script...")
                    GLib.idle_add(lambda: self.update_terminal(terminal_view, "Downloading uninstall script...\n"))
                    script_file = self.download_script(uninstall_url)
                    
                    if not script_file:
                        error_msg = "Failed to download uninstall script!"
                        GLib.idle_add(update_progress, 1.0, error_msg)
                        GLib.idle_add(lambda: self.update_terminal(terminal_view, error_msg + "\n"))
                        time.sleep(2)
                        GLib.idle_add(progress_dialog.destroy)
                        return

                    # Make script executable
                    os.chmod(script_file, 0o755)
                    status_msg = "Preparing uninstallation..."
                    GLib.idle_add(update_progress, 0.2, status_msg)
                    GLib.idle_add(lambda: self.update_terminal(terminal_view, status_msg + "\n"))

                    # Count the number of significant lines in the script to track progress
                    total_lines = 0
                    significant_lines = []
                    try:
                        with open(script_file, 'r') as f:
                            for line in f:
                                # Skip empty lines and comments
                                line = line.strip()
                                if line and not line.startswith('#'):
                                    total_lines += 1
                                    significant_lines.append(line)
                        # Ensure we have at least one line
                        total_lines = max(1, total_lines)
                        GLib.idle_add(lambda: self.update_terminal(terminal_view, f"Script contains {total_lines} executable steps\n"))
                    except Exception as e:
                        print(f"Error counting script lines: {e}")
                        # Default to a reasonable number if counting fails
                        total_lines = 100
                    
                    # Calculate base progress (downloading and preparation = 20%)
                    base_progress = 0.2
                    # Calculate line progress (each line contributes to 70% of progress)
                    line_progress_weight = 0.7 / total_lines
                    
                    # Execute script with better progress tracking
                    status_msg = "Starting uninstallation..."
                    GLib.idle_add(update_progress, base_progress, status_msg)
                    GLib.idle_add(lambda: self.update_terminal(terminal_view, status_msg + "\n"))

                    uninstall_process = subprocess.Popen(
                        [script_file],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1,
                        preexec_fn=os.setsid
                    )

                    # Track current line
                    current_line = 0
                    cancel_button_disabled = False

                    for line in uninstall_process.stdout:
                        if uninstall_cancelled:
                            os.killpg(os.getpgid(uninstall_process.pid), signal.SIGTERM)
                            msg = "Uninstallation cancelled!"
                            GLib.idle_add(update_progress, 1.0, msg)
                            GLib.idle_add(lambda: self.update_terminal(terminal_view, msg + "\n"))
                            time.sleep(1)
                            GLib.idle_add(progress_dialog.destroy)
                            return
                            
                        # Check if this is a heavy operation that should disable cancel button
                        if not cancel_button_disabled and self.is_heavy_operation(line) and cancel_button:
                            GLib.idle_add(lambda: cancel_button.set_sensitive(False))
                            GLib.idle_add(lambda: cancel_button.set_tooltip_text("Uninstallation is processing critical operations and cannot be cancelled"))
                            GLib.idle_add(lambda: self.update_terminal(terminal_view, "\nUninstallation is processing critical operations and cannot be cancelled\n"))
                            cancel_button_disabled = True
                        
                        # Update current line and calculate progress
                        current_line += 1
                        # Ensure we don't exceed our total for any reason
                        current_line = min(current_line, total_lines)
                        
                        # Calculate current progress
                        # For heavy operations, use a gradual progress update
                        line_str = line.strip()
                        if self.is_heavy_operation(line_str):
                            # Start progress from current point
                            current_progress = base_progress + (current_line - 1) * line_progress_weight
                            # End progress is what it would be after this operation
                            next_progress = base_progress + current_line * line_progress_weight
                            # Cap at 90%
                            next_progress = min(0.9, next_progress)
                            
                            # Update terminal immediately
                            GLib.idle_add(lambda l=line: self.update_terminal(terminal_view, l))
                            
                            # Gradually update progress for this heavy operation (5-8 seconds based on operation)
                            duration = 5.0  # Base duration for heavy ops
                            if "download_file" in line_str.lower() or "aria2c" in line_str.lower() or "wget" in line_str.lower():
                                duration = 8.0  # Longer for downloads
                            elif "extract" in line_str.lower() or "tar" in line_str.lower() or "unzip" in line_str.lower():
                                duration = 6.0  # Medium for extractions
                            elif "package_remove" in line_str.lower() or "apt-get remove" in line_str.lower():
                                duration = 7.0  # Longer for package removals
                                
                            self.update_progress_gradually(update_progress, current_progress, next_progress, line_str, duration)
                            
                            # We don't need to display this line with the update_progress call below
                            # Just move to the next line without additional updates
                            continue
                        else:
                            # For normal operations, update immediately
                            current_progress = base_progress + (current_line * line_progress_weight)
                            
                            # Cap progress at 90% - the final 10% is reserved for completion tasks
                            current_progress = min(0.9, current_progress)
                            
                            # Update progress
                            GLib.idle_add(update_progress, current_progress, line.strip())
                            
                            # Update terminal
                            GLib.idle_add(lambda l=line: self.update_terminal(terminal_view, l))

                    uninstall_process.wait()
                    if uninstall_process.returncode == 0 and not uninstall_cancelled:
                        msg = "Finalizing uninstallation..."
                        GLib.idle_add(update_progress, 0.95, msg)
                        GLib.idle_add(lambda: self.update_terminal(terminal_view, msg + "\n"))
                        
                        # Disable cancel button as uninstallation is almost complete
                        if cancel_button:
                            GLib.idle_add(lambda: cancel_button.set_sensitive(False))
                            GLib.idle_add(lambda: cancel_button.set_tooltip_text("Uninstallation is almost complete and cannot be cancelled"))
                            GLib.idle_add(lambda: self.update_terminal(terminal_view, "\nUninstallation is almost complete and cannot be cancelled\n"))
                        
                        self.installed_apps.remove(app['folder_name'])
                        self.save_installed_apps()
                        # Get current category before refreshing
                        current_category = self._get_selected_category()
                        GLib.idle_add(lambda cat=current_category: self.show_apps(cat))
                        msg = "Uninstallation complete!"
                        GLib.idle_add(update_progress, 1.0, msg)
                        GLib.idle_add(lambda: self.update_terminal(terminal_view, msg + "\n"))
                        
                        # Close log file if logging is active
                        if self.logging_active and self.log_file:
                            try:
                                self.log_file.write("\n--- Uninstallation completed successfully ---\n")
                                self.log_file.close()
                            except Exception:
                                pass
                            self.log_file = None
                            self.logging_active = False
                            self.log_file_path = None
                        
                        time.sleep(1)
                    else:
                        msg = "Uninstallation failed!"
                        GLib.idle_add(update_progress, 1.0, msg)
                        GLib.idle_add(lambda: self.update_terminal(terminal_view, msg + "\n"))
                        
                        # Close log file if logging is active
                        if self.logging_active and self.log_file:
                            try:
                                self.log_file.write("\n--- Uninstallation failed ---\n")
                                self.log_file.close()
                            except Exception:
                                pass
                            self.log_file = None
                            self.logging_active = False
                            self.log_file_path = None
                        
                        time.sleep(2)
                    GLib.idle_add(progress_dialog.destroy)

                except Exception as e:
                    error_msg = f"Uninstallation error: {str(e)}"
                    print(error_msg)
                    GLib.idle_add(update_progress, 1.0, f"Error: {str(e)}")
                    GLib.idle_add(lambda: self.update_terminal(terminal_view, error_msg + "\n"))
                    
                    # Close log file if logging is active
                    if self.logging_active and self.log_file:
                        try:
                            self.log_file.write(f"\n--- Uninstallation error: {str(e)} ---\n")
                            self.log_file.close()
                        except Exception:
                            pass
                        self.log_file = None
                        self.logging_active = False
                        self.log_file_path = None
                    
                    time.sleep(2)
                    GLib.idle_add(progress_dialog.destroy)

            thread = threading.Thread(target=uninstall_thread)
            thread.daemon = True
            thread.start()
            
            # Connect the response signal
            progress_dialog.connect('response', on_cancel_clicked)
            
            # Connect the cancel button if found
            if cancel_button:
                cancel_button.connect("clicked", on_cancel_clicked)
            else:
                print("Warning: Cancel button not found in uninstall dialog")

    def show_apps(self, category=None):
        """Display apps based on category"""
        try:
            # Clear current list safely
            GLib.idle_add(self.clear_app_list_box)
            
            # Filter apps based on category and search query
            filtered_apps = self.apps_data
            if category and category != "All Apps":
                filtered_apps = [app for app in filtered_apps if category in app['categories']]
                # print(f"Filtered by category '{category}': {len(filtered_apps)} apps")
                
            # Apply search filter if search entry has text
            search_text = self.search_entry.get_text().lower()
            if search_text:
                # print(f"Filtering by search term: '{search_text}'")
                original_count = len(filtered_apps)
                
                # Check if fuzzy search is enabled
                if self.get_setting("enable_fuzzy_search", False) and (fuzz is not None):
                    # Use fuzzy search
                    fuzzy_threshold = 60  # Minimum score to consider a match (0-100)
                    fuzzy_matches = []
                    
                    for app in filtered_apps:
                        # Check app name
                        name_score = fuzz.partial_ratio(search_text, app['app_name'].lower())
                        
                        # Check description
                        desc_score = fuzz.partial_ratio(search_text, app['description'].lower())
                        
                        # Check categories
                        cat_score = 0
                        for cat in app['categories']:
                            cat_score = max(cat_score, fuzz.partial_ratio(search_text, cat.lower()))
                        
                        # Use the best score
                        max_score = max(name_score, desc_score, cat_score)
                        
                        if max_score >= fuzzy_threshold:
                            # Store the app and its score for sorting
                            fuzzy_matches.append((app, max_score))
                    
                    # Sort by score (highest first) and extract just the apps
                    fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
                    filtered_apps = [app for app, score in fuzzy_matches]
                else:
                    # First, try to find matches in app names only
                    name_matches = [app for app in filtered_apps if search_text in app['app_name'].lower()]
                    
                    # If no matches in names, try descriptions and categories
                    if not name_matches:
                        desc_matches = [app for app in filtered_apps 
                                       if search_text in app['description'].lower()]
                        cat_matches = [app for app in filtered_apps 
                                      if any(search_text in cat.lower() for cat in app['categories'])]
                        
                        # Combine description and category matches, ensuring no duplicates
                        filtered_apps = list({app['app_name']: app for app in desc_matches + cat_matches}.values())
                    else:
                        # Use the name matches
                        filtered_apps = name_matches
                # print(f"Search filtered {original_count} -> {len(filtered_apps)} apps")
            
            # Add filtered apps to the list using idle_add
            if filtered_apps:
                # print(f"Displaying {len(filtered_apps)} apps")
                for app in filtered_apps:
                    GLib.idle_add(lambda a=app: self.add_app_card(a))
            else:
                # print("No apps match the current filters")
                # Show a message that no apps match
                GLib.idle_add(self._show_no_apps_message, search_text)

            GLib.idle_add(self.app_list_box.show_all)
        except Exception as e:
            print(f"Error in show_apps: {e}")
            import traceback
            traceback.print_exc()

    def _show_no_apps_message(self, search_text):
        """Show a message when no apps match the search"""
        message_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        message_box.set_valign(Gtk.Align.CENTER)
        message_box.set_halign(Gtk.Align.CENTER)
        
        # Add an icon
        icon = Gtk.Image.new_from_icon_name("system-search", Gtk.IconSize.DIALOG)
        message_box.pack_start(icon, False, False, 0)
        
        # Add message
        if search_text:
            message = Gtk.Label()
            message.set_markup(f"<span size='larger'>No apps match: <i>{GLib.markup_escape_text(search_text)}</i></span>")
            message_box.pack_start(message, False, False, 0)
            
            # Add explanation about how search works
            explanation = Gtk.Label()
            explanation.set_markup("<span>We've searched in app names, descriptions, and categories.</span>")
            message_box.pack_start(explanation, False, False, 0)
            
            # Add suggestion
            suggestion = Gtk.Label()
            suggestion.set_markup("<span>Try a different search term</span>")
            message_box.pack_start(suggestion, False, False, 10)
        else:
            message = Gtk.Label()
            message.set_markup("<span size='larger'>No apps available</span>")
            message_box.pack_start(message, False, False, 0)
        
        self.app_list_box.pack_start(message_box, True, True, 0)

    def clear_app_list_box(self):
        """Clear the app list box, removing all children"""
        # Safety check - if app_list_box doesn't exist yet, just return
        if not hasattr(self, 'app_list_box'):
            print("Warning: app_list_box not initialized yet in clear_app_list_box")
            return False
            
        try:
            # Print the current number of children for debugging
            children_count = len(self.app_list_box.get_children())
            # print(f"Clearing app list box with {children_count} children")
            
            # Remove all children
            for child in self.app_list_box.get_children():
                self.app_list_box.remove(child)
            
            # print("App list box cleared")
        except Exception as e:
            print(f"Error in clear_app_list_box: {e}")
            
        return False  # For use with GLib.idle_add

    def add_app_card(self, app):
        """Add a single app card to the list box"""
        try:
            # Create app card
            app_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            app_card.get_style_context().add_class('app-card')

            # Create card content
            card_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            card_box.set_margin_start(12)
            card_box.set_margin_end(12)
            card_box.set_margin_top(12)
            card_box.set_margin_bottom(12)

            # Check if this app is a result of description search
            search_text = self.search_entry.get_text().lower()
            found_in_description = False
            if search_text and search_text not in app['app_name'].lower() and search_text in app['description'].lower():
                found_in_description = True

            # App logo with error handling
            logo_path = None
            # Try PNG first
            png_path = os.path.join(APPSTORE_LOGO_DIR, app['folder_name'], 'logo.png')
            # Try SVG if PNG doesn't exist
            svg_path = os.path.join(APPSTORE_LOGO_DIR, app['folder_name'], 'logo.svg')
            
            if os.path.exists(png_path):
                logo_path = png_path
            elif os.path.exists(svg_path):
                logo_path = svg_path
                
            if logo_path:
                try:
                    # Load image in a safer way
                    pixbuf = None
                    try:
                        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(logo_path, 64, 64, True)
                    except GLib.Error as e:
                        print(f"Error loading logo for {app['app_name']}: {e}")
                    except Exception as e:
                        print(f"Unexpected error loading logo for {app['app_name']}: {e}")

                    if pixbuf:
                        logo_image = Gtk.Image.new_from_pixbuf(pixbuf)
                        logo_image.set_margin_end(12)
                        card_box.pack_start(logo_image, False, False, 0)
                except Exception as e:
                    print(f"Error creating logo image for {app['app_name']}: {e}")

            # App info
            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            
            # Top row with app name and source type
            top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            
            # App name
            name_label = Gtk.Label()
            name_label.set_markup(f"<b>{GLib.markup_escape_text(app['app_name'])}</b>")
            name_label.set_halign(Gtk.Align.START)
            top_row.pack_start(name_label, False, False, 0)
            
            # Spacer
            top_row.pack_start(Gtk.Label(), True, True, 0)
            
            # Source type label
            source_label = Gtk.Label()
            source_type = app.get('app_type', 'unknown').capitalize()
            source_label.set_markup(f"Source: {GLib.markup_escape_text(source_type)}")
            source_label.get_style_context().add_class("metadata-label")
            source_label.set_size_request(120, -1)
            source_label.set_halign(Gtk.Align.CENTER)
            source_label.set_margin_end(6)
            top_row.pack_end(source_label, False, False, 0)
            
            info_box.pack_start(top_row, False, False, 0)

            # App description with proper escaping
            desc_text = app['description'][:100] + "..." if len(app['description']) > 100 else app['description']
            desc_label = Gtk.Label(label=GLib.markup_escape_text(desc_text))
            desc_label.set_line_wrap(True)
            desc_label.set_halign(Gtk.Align.START)
            info_box.pack_start(desc_label, False, False, 0)

            # Bottom row box for buttons and version
            bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            bottom_box.set_margin_top(6)

            # Button box (left side of bottom row)
            button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

            # Version label (right side of bottom row)
            version_label = Gtk.Label()
            version = app.get('version', '')
            if version and isinstance(version, str):
                if version in ['termux_local_version', 'distro_local_version']:
                    version = 'Unavailable'
                else:
                    version = version.split(',')[0].strip()
                    version = version.split()[0].strip()
                    # Remove leading 'v' if present
                    if version.startswith('v'):
                        version = version[1:]
            else:
                version = 'Unavailable'
            version_label.set_text(GLib.markup_escape_text(version))
            version_label.get_style_context().add_class("metadata-label")
            version_label.set_size_request(120, -1)
            version_label.set_halign(Gtk.Align.CENTER)
            version_label.set_margin_end(6)

            # Add buttons based on installation status
            is_installed = app['folder_name'] in self.installed_apps

            if is_installed:
                has_update = app['folder_name'] in self.pending_updates
                if has_update and app.get('install_url'):
                    update_button = Gtk.Button(label="Update")
                    update_button.get_style_context().add_class("update-button")
                    update_button.connect("clicked", self.on_update_clicked, app)
                    update_button.set_size_request(120, -1)
                    button_box.pack_start(update_button, False, False, 0)
                elif app.get('run_cmd') and app.get('run_cmd').strip():  # Check if run_cmd exists and is not empty
                    open_button = Gtk.Button(label="Open")
                    open_button.get_style_context().add_class("open-button")
                    open_button.connect("clicked", self.on_open_clicked, app)
                    open_button.set_size_request(120, -1)
                    button_box.pack_start(open_button, False, False, 0)

                uninstall_button = Gtk.Button(label="Uninstall")
                uninstall_button.get_style_context().add_class("uninstall-button")
                uninstall_button.connect("clicked", self.on_uninstall_clicked, app)
                uninstall_button.set_size_request(120, -1)
                button_box.pack_start(uninstall_button, False, False, 0)
            else:
                install_button = Gtk.Button(label="Install")
                install_button.get_style_context().add_class("install-button")
                install_button.connect("clicked", self.on_install_clicked, app)
                install_button.set_size_request(120, -1)
                button_box.pack_start(install_button, False, False, 0)

            bottom_box.pack_start(button_box, False, False, 0)
            bottom_box.pack_end(version_label, False, False, 0)
            info_box.pack_start(bottom_box, False, False, 0)
            
            card_box.pack_start(info_box, True, True, 0)
            app_card.add(card_box)
            self.app_list_box.pack_start(app_card, False, True, 0)

            return False
        except Exception as e:
            print(f"Error adding app card for {app['app_name']}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def on_search_changed(self, entry):
        """Handle search entry changes"""
        # Get the current search text
        search_text = entry.get_text().lower()
        # print(f"Search changed: '{search_text}'")
        
        # Remove any existing timeout
        if hasattr(self, 'search_timeout_id') and self.search_timeout_id:
            GLib.source_remove(self.search_timeout_id)
            self.search_timeout_id = None
        
        # Add a small delay to avoid unnecessary refreshes while typing
        self.search_timeout_id = GLib.timeout_add(300, self._do_search, search_text)
    
    def on_search_entry_activate(self, entry):
        """Handle Enter key in search entry - give focus back to the app list"""
        if hasattr(self, 'app_list_box'):
            self.app_list_box.grab_focus()

    def _do_search(self, search_text):
        """Process the search after delay"""
        self.search_timeout_id = None  # Clear the timeout ID
        
        # Check all potential classes for tab selection
        explorer_selected = (self.explore_button.get_style_context().has_class('selected') or 
                            self.explore_button.get_style_context().has_class('active'))
        installed_selected = (self.installed_button.get_style_context().has_class('selected') or 
                             self.installed_button.get_style_context().has_class('active'))
        updates_selected = (self.updates_button.get_style_context().has_class('selected') or 
                           self.updates_button.get_style_context().has_class('active'))
        
        # Log all tab states for debugging
        # print(f"Tab states - Explore: {explorer_selected}, Installed: {installed_selected}, Updates: {updates_selected}")
        
        # Determine which section is selected
        selected_section = None
        if explorer_selected:
            selected_section = "explore"
        elif installed_selected:
            selected_section = "installed"
        elif updates_selected:
            selected_section = "updates"
        else:
            # Default to explore if nothing is selected
            selected_section = "explore"
            print("No tab appears to be selected, defaulting to 'explore'")
            
        # print(f"Selected section: {selected_section}")
        
        # Update the appropriate view
        if selected_section == "explore":
            # Get the currently selected category
            selected_category = None
            for button in self.category_buttons:
                if button.get_style_context().has_class('selected'):
                    selected_category = button.get_label()
                    break
            if selected_category == "All Apps":
                selected_category = None
                
            # print(f"Selected category: {selected_category}")
            self.show_apps(selected_category)
        elif selected_section == "installed":
            self.show_installed_apps()
        elif selected_section == "updates":
            self.show_update_apps()
            
        return False  # Don't repeat the timeout

    def on_delete_event(self, widget, event):
        """Handle window close event"""
        try:
            # Stop background tasks
            self.stop_background_tasks = True
            
            # Shutdown thread pool
            if hasattr(self, 'thread_pool'):
                self.thread_pool.shutdown(wait=False)
            
            # Save any pending state
            self.save_installed_apps()
            self.save_pending_updates()
            
            # Quit the application
            self.get_application().quit()
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
            
        return False

    def refresh_error(self, error_message):
        """Handle refresh error"""
        print(f"Refresh error: {error_message}")
        
        # Reset the refreshing flag
        self.is_refreshing = False
        
        # Hide the loading indicators
        self.spinner.stop()
        self.spinner.hide()
        self.loading_label.hide()
        # self.refresh_button.set_sensitive(True)
        
        # Show the header bar again in case of error
        header_bar = self.get_titlebar()
        if header_bar:
            header_bar.show()
        
        # Show error dialog
        self.show_error_dialog(f"Refresh failed: {error_message}")
        
        # Setup UI with existing data
        self.setup_app_list_ui()

    def download_apps(self):
        """Download apps in the background"""
        # Implement multi-threading logic for downloading apps
        pass

    def on_open_clicked(self, button, app):
        """Handle open button click"""
        try:
            run_cmd = app.get('run_cmd')
            if not run_cmd:
                self.show_error_dialog("No run command specified for this app")
                return

            # Prefix pdrun for distro apps
            if app.get('app_type') == 'distro':
                run_cmd = f"pdrun {run_cmd}"

            # Check if we should show command output
            if self.get_setting("show_command_output", False):
                self.show_command_output_window(app.get('name', 'Application'), run_cmd)
            else:
                # Just run the command
                subprocess.Popen(['bash', '-c', run_cmd])
        except Exception as e:
            self.show_error_dialog(f"Error opening app: {e}")
            
    def show_command_output_window(self, app_name, run_cmd):
        """Show a window with the command output"""
        # Create dialog
        dialog = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        dialog.set_title(f"Running {app_name}")
        dialog.set_default_size(600, 400)
        dialog.set_border_width(10)
        dialog.set_position(Gtk.WindowPosition.CENTER)
        dialog.set_destroy_with_parent(True)
        dialog.get_style_context().add_class("command-output-dialog")
        
        # Set window icon
        icon_name = "utilities-terminal"
        icon_theme = Gtk.IconTheme.get_default()
        if icon_theme.has_icon(icon_name):
            dialog.set_icon_name(icon_name)
            
        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        dialog.add(main_box)
        
        # Create scrolled window for terminal
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)
        
        # Create TextView for terminal output
        terminal_view = Gtk.TextView()
        terminal_view.set_editable(False)
        terminal_view.set_cursor_visible(False)
        terminal_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        terminal_view.get_style_context().add_class("terminal-view")
        
        # Initialize terminal emulator
        terminal_emulator = TerminalEmulator(terminal_view)
        
        scrolled_window.add(terminal_view)
        main_box.pack_start(scrolled_window, True, True, 0)
        
        # Create button box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(12)
        main_box.pack_start(button_box, False, False, 0)
        
        # Create save button
        save_button = Gtk.Button(label="Save Output")
        save_button.set_tooltip_text("Save command output to a file")
        save_button.get_style_context().add_class("command-output-save-button")
        button_box.pack_start(save_button, False, False, 0)
        
        # Create close button
        close_button = Gtk.Button(label="Close")
        close_button.set_tooltip_text("Close this window")
        close_button.get_style_context().add_class("command-output-close-button")
        button_box.pack_start(close_button, False, False, 0)
        
        # Initial text
        terminal_emulator.append_text(f"Starting {app_name}...\n")
        
        # Show all widgets
        dialog.show_all()
        
        # Function to update the terminal
        def update_terminal_output(text):
            terminal_emulator.append_text(text)
        
        # Function to save output to file
        def on_save_clicked(button):
            text = terminal_emulator.get_text()
            
            # Create file chooser dialog
            file_dialog = Gtk.FileChooserDialog(
                title="Save Output",
                parent=dialog,
                action=Gtk.FileChooserAction.SAVE
            )
            file_dialog.add_buttons(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_SAVE, Gtk.ResponseType.OK
            )
            
            # Set default filename and location
            home_dir = os.path.expanduser("~")
            file_dialog.set_current_folder(home_dir)
            file_dialog.set_current_name(f"{app_name.lower().replace(' ', '_')}_output.log")
            
            # Show the dialog
            response = file_dialog.run()
            if response == Gtk.ResponseType.OK:
                filename = file_dialog.get_filename()
                try:
                    # Save current content
                    with open(filename, 'w') as f:
                        # Write the clean text without ANSI codes
                        f.write(AnsiColorParser().strip_ansi(text))
                    update_terminal_output(f"\nOutput saved to {filename}\n")
                except Exception as e:
                    update_terminal_output(f"\nError saving output: {e}\n")
            
            file_dialog.destroy()
        
        # Connect save button click
        save_button.connect("clicked", on_save_clicked)
        
        # Connect close button
        close_button.connect("clicked", lambda b: dialog.destroy())
        
        # Start process
        try:
            # Run the command
            process = subprocess.Popen(
                ['bash', '-c', run_cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Function to read output
            def read_output():
                for line in iter(process.stdout.readline, ''):
                    GLib.idle_add(update_terminal_output, line)
                process.stdout.close()
                # Add completed message
                GLib.idle_add(update_terminal_output, f"\nCommand completed with return code: {process.wait()}\n")
                return False
            
            # Start thread to read output
            output_thread = threading.Thread(target=read_output)
            output_thread.daemon = True
            output_thread.start()
            
        except Exception as e:
            update_terminal_output(f"Error running command: {e}\n")
        
        return dialog

    def start_task_processor(self):
        """Start the background task processor thread"""
        self.task_running = True
        self.task_thread = threading.Thread(target=self.process_tasks)
        self.task_thread.daemon = True
        self.task_thread.start()

    def process_tasks(self):
        """Process tasks from the queue"""
        while self.task_running:
            try:
                task = self.task_queue.get(timeout=1.0)
                if task:
                    task()
                self.task_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing task: {str(e)}")

    def stop_task_processor(self):
        """Stop the task processor thread"""
        self.task_running = False
        if self.task_thread:
            self.task_thread.join()

    def on_destroy(self, *args):
        """Clean up when window is closed"""
        # Close any open log files
        if hasattr(self, 'log_file') and self.log_file:
            try:
                self.log_file.write("\n--- Application closed ---\n")
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None
            self.logging_active = False
            self.log_file_path = None
            
        self.stop_task_processor()
        sys.exit(0)

    def on_quit_accelerator(self, accel_group, acceleratable, keyval, modifier):
        """Handle Ctrl+Q accelerator"""
        self.on_delete_event(None, None)
        return True
        
    def on_search_accelerator(self, accel_group, acceleratable, keyval, modifier):
        """Handle Ctrl+F accelerator to toggle search bar"""
        self.on_search_button_clicked(None)
        return True

    def load_pending_updates(self):
        """Load pending updates from tracking file"""
        try:
            if os.path.exists(self.updates_tracking_file):
                print(f"Loading updates from {self.updates_tracking_file}")
                with open(self.updates_tracking_file, 'r') as f:
                    updates = json.load(f)
                    print(f"Loaded updates: {updates}")
                    return updates
            else:
                print(f"No updates file found at {self.updates_tracking_file}")
                return {}
        except Exception as e:
            print(f"Error loading updates tracking: {e}")
            return {}

    def save_pending_updates(self):
        """Save pending updates to tracking file"""
        try:
            # APPSTORE_DIR is already created in setup_directories
            print(f"Saving updates to {self.updates_tracking_file}")
            print(f"Updates to save: {self.pending_updates}")
            with open(self.updates_tracking_file, 'w') as f:
                json.dump(self.pending_updates, f, indent=2)
            print(f"Successfully saved updates")
        except Exception as e:
            print(f"Error saving updates tracking: {e}")
            import traceback
            traceback.print_exc()

    def compare_versions(self, old_data, new_data):
        """Compare versions between old and new apps.json"""
        updates = {}
        print("\nComparing versions:")
        for new_app in new_data:
            app_name = new_app['folder_name']
            new_version = new_app.get('version')
            
            # Find corresponding app in old data
            old_app = next((app for app in old_data if app['folder_name'] == app_name), None)
            if old_app:
                old_version = old_app.get('version')
                print(f"Comparing {app_name}: old={old_version}, new={new_version}")
                if new_version and old_version != new_version:
                    print(f"Update found for {app_name}: {old_version} -> {new_version}")
                    updates[app_name] = new_version
        
        print(f"Total updates found: {len(updates)}")
        print(f"Updates: {updates}")
        return updates

    def create_update_dialog(self, title="Updating...", allow_cancel=True):
        """Create a dialog for update progress with terminal view"""
        # Create dialog
        update_dialog = Gtk.Dialog(
            title=title,
            parent=self,
            modal=True,
            destroy_with_parent=True
        )
        
        # Variables for continuous logging are already set at the class level
        
        # Create and set custom header bar
        header_bar = Gtk.HeaderBar()
        header_bar.set_show_close_button(False)
        header_bar.set_title(title)
        
        # Add terminal toggle button to header bar
        terminal_button = Gtk.Button.new_from_icon_name("utilities-terminal-symbolic", Gtk.IconSize.BUTTON)
        terminal_button.set_tooltip_text("Toggle Terminal View")
        header_bar.pack_end(terminal_button)
        
        # Add save button to header bar
        save_button = Gtk.Button.new_from_icon_name("document-save-symbolic", Gtk.IconSize.BUTTON)
        save_button.set_tooltip_text("Save Log to File")
        header_bar.pack_end(save_button)
        
        # Set the header bar
        update_dialog.set_titlebar(header_bar)
        
        # Add close button if cancellation is allowed
        if allow_cancel:
            cancel_button = update_dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
            cancel_button.get_style_context().add_class('destructive-action')
        
        # Create stack for switching between progress and terminal views
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        stack.set_transition_duration(150)
        
        # Progress view
        progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        progress_box.set_margin_start(10)
        progress_box.set_margin_end(10)
        progress_box.set_margin_top(10)
        progress_box.set_margin_bottom(10)
        
        # Status label with better text handling
        status_label = Gtk.Label()
        status_label.set_line_wrap(True)
        status_label.set_line_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        status_label.set_justify(Gtk.Justification.LEFT)
        status_label.set_halign(Gtk.Align.START)
        status_label.set_text("Starting update...")
        
        # Create a scrolled window for status label that expands
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_size_request(-1, 60)
        scroll.add(status_label)
        progress_box.pack_start(scroll, True, True, 0)
        
        # Progress bar that expands horizontally
        progress_bar = Gtk.ProgressBar()
        progress_bar.set_show_text(True)
        progress_bar.set_size_request(-1, 20)
        progress_box.pack_start(progress_bar, False, True, 0)
        
        # Terminal view
        terminal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        terminal_box.set_margin_start(10)
        terminal_box.set_margin_end(10)
        terminal_box.set_margin_top(10)
        terminal_box.set_margin_bottom(10)
        
        terminal_scroll = Gtk.ScrolledWindow()
        terminal_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        terminal_scroll.set_size_request(400, 150)  # Reduced from 200
        terminal_scroll.set_vexpand(True)
        terminal_scroll.set_hexpand(True)
        
        # Create terminal view with monospace font
        terminal_view = Gtk.TextView()
        terminal_view.set_editable(False)
        terminal_view.set_cursor_visible(False)
        terminal_view.set_monospace(True)
        terminal_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        
        # Set terminal colors using CSS classes
        terminal_view.get_style_context().add_class('terminal-view')
        
        # Initialize the terminal emulator
        terminal_emulator = TerminalEmulator(terminal_view)
        
        # Add terminal view to scroll window
        terminal_scroll.add(terminal_view)
        terminal_box.pack_start(terminal_scroll, True, True, 0)
        
        # Add views to stack
        stack.add_named(progress_box, "progress")
        stack.add_named(terminal_box, "terminal")
        stack.set_visible_child_name("progress")
        
        # Add stack to dialog's content area with margins
        content_area = update_dialog.get_content_area()
        content_area.add(stack)
        
        # Make the dialog resizable and set compact default size
        update_dialog.set_resizable(True)
        update_dialog.set_default_size(400, 200)  # Reduced from 500x300
        
        def toggle_terminal(button):
            current = stack.get_visible_child_name()
            stack.set_visible_child_name("terminal" if current == "progress" else "progress")
            button.set_tooltip_text("Show Progress" if current == "progress" else "Show Terminal")
        
        terminal_button.connect("clicked", toggle_terminal)
        
        # Show all widgets
        update_dialog.show_all()
        
        return update_dialog, status_label, progress_bar, terminal_view

    def on_update_clicked(self, button, app):
        """Handle update button click"""
        try:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text=f"Update {app['app_name']}?"
            )
            response = dialog.run()
            dialog.destroy()

            if response == Gtk.ResponseType.YES:
                # Create update dialog with terminal functionality
                update_dialog, status_label, progress_bar, terminal_view = self.create_update_dialog(
                    title=f"Updating {app['app_name']}...",
                    allow_cancel=True
                )

                # Initialize variables for nonlocal access
                update_process = None
                update_cancelled = False
                script_file = None
                
                # Get cancel button using the dialog's action area
                cancel_button = None
                for button in update_dialog.get_action_area().get_children():
                    if isinstance(button, Gtk.Button) and button.get_label() in ["Cancel", "_Cancel"]:
                        cancel_button = button
                        break

                def on_cancel_clicked(*args):
                    nonlocal update_process, update_cancelled, update_dialog, script_file
                    update_cancelled = True
                    
                    # Properly terminate the process if it exists
                    if update_process and update_process.poll() is None:
                        try:
                            # First try SIGTERM
                            os.killpg(os.getpgid(update_process.pid), signal.SIGTERM)
                            
                            # Wait a second for process to terminate
                            start_time = time.time()
                            while time.time() - start_time < 1 and update_process.poll() is None:
                                time.sleep(0.1)
                            
                            # If process still running, use SIGKILL
                            if update_process.poll() is None:
                                os.killpg(os.getpgid(update_process.pid), signal.SIGKILL)
                                
                            terminal_update = "Update cancelled by user. Terminating process..."
                            GLib.idle_add(lambda: self.update_terminal(terminal_view, terminal_update))
                        except Exception as e:
                            print(f"Error terminating process: {e}")
                    
                    # Clean up the script file
                    if script_file and os.path.exists(script_file):
                        try:
                            os.remove(script_file)
                        except Exception as e:
                            print(f"Error removing script file: {e}")
                    
                    # Add a small delay before destroying the dialog
                    GLib.timeout_add(500, lambda: update_dialog.destroy() if update_dialog else None)
                    return True

                # Connect the response signal
                update_dialog.connect('response', on_cancel_clicked)
                
                if cancel_button:
                    cancel_button.connect("clicked", on_cancel_clicked)
                else:
                    print("Warning: Cancel button not found in update dialog")

                def update_progress(fraction, status_text):
                    if not status_text:
                        return False
                    
                    # Check if dialog is still valid
                    if not update_dialog or not update_dialog.get_window():
                        return False
                    
                    # Update both progress view and terminal view
                    if '[#' in status_text and ']' in status_text:
                        # Extract progress details from aria2c output
                        progress_part = status_text[status_text.find('['):status_text.find(']')+1]
                        file_part = status_text[status_text.find(']')+1:].strip()
                        
                        # Format the status text to show both progress and file
                        status_label.set_text(f"{progress_part}\n{file_part}")
                    elif isinstance(status_text, str) and status_text.strip():
                        status_label.set_text(status_text)
                    
                    # Get the stack widget from the progress dialog
                    stack = None
                    try:
                        for child in update_dialog.get_content_area().get_children():
                            if isinstance(child, Gtk.Stack):
                                stack = child
                                break
                    except Exception:
                        return False
                    
                    # Always update terminal view
                    GLib.idle_add(lambda: self.update_terminal(terminal_view, status_text))
                    
                    # Make sure terminal view is shown if setting is enabled
                    if stack and self.get_setting("use_terminal_for_progress", False):
                        GLib.idle_add(lambda s=stack: s.set_visible_child_name("terminal"))
                    
                    # Disable cancel button if installation is near completion (90% or more)
                    if fraction >= 0.9 and cancel_button:
                        GLib.idle_add(lambda: cancel_button.set_sensitive(False))
                        if not hasattr(cancel_button, 'tooltip_set'):
                            cancel_button.set_tooltip_text("Update is almost complete and cannot be cancelled")
                            setattr(cancel_button, 'tooltip_set', True)
                            GLib.idle_add(lambda: self.update_terminal(terminal_view, "\nUpdate is almost complete and cannot be cancelled\n"))
                    
                    progress_bar.set_fraction(fraction)
                    progress_bar.set_text(f"{int(fraction * 100)}%")
                    return False

                def update_thread():
                    nonlocal script_file, update_process
                    try:
                        # Download script (20%)
                        GLib.idle_add(update_progress, 0.2, "Downloading update script...")
                        script_file = self.download_script(app['install_url'])
                        if not script_file or update_cancelled:
                            if script_file and os.path.exists(script_file):
                                os.remove(script_file)
                            GLib.idle_add(update_dialog.destroy)
                            return

                        # Make script executable (30%)
                        GLib.idle_add(update_progress, 0.3, "Preparing update...")
                        os.chmod(script_file, os.stat(script_file).st_mode | stat.S_IEXEC)

                        # Count the number of significant lines in the script to track progress
                        total_lines = 0
                        significant_lines = []
                        try:
                            with open(script_file, 'r') as f:
                                for line in f:
                                    # Skip empty lines and comments
                                    line = line.strip()
                                    if line and not line.startswith('#'):
                                        total_lines += 1
                                        significant_lines.append(line)
                            # Ensure we have at least one line
                            total_lines = max(1, total_lines)
                            GLib.idle_add(lambda: self.update_terminal(terminal_view, f"Script contains {total_lines} executable steps\n"))
                        except Exception as e:
                            print(f"Error counting script lines: {e}")
                            # Default to a reasonable number if counting fails
                            total_lines = 100
                        
                        # Calculate base progress (downloading and preparation = 30%)
                        base_progress = 0.3
                        # Calculate line progress (each line contributes to 60% of progress)
                        line_progress_weight = 0.6 / total_lines

                        # Execute script with better progress tracking
                        GLib.idle_add(update_progress, base_progress, "Starting update...")
                        update_process = subprocess.Popen(
                            ['bash', script_file],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            universal_newlines=True,
                            bufsize=1,
                            preexec_fn=os.setsid
                        )

                        # Track current line
                        current_line = 0
                        cancel_button_disabled = False

                        while True:
                            if update_cancelled:
                                try:
                                    os.killpg(os.getpgid(update_process.pid), signal.SIGTERM)
                                    update_process.wait(timeout=2)
                                except:
                                    pass
                                GLib.idle_add(update_dialog.destroy)
                                return

                            line = update_process.stdout.readline()
                            if not line and update_process.poll() is not None:
                                break

                            line = line.strip()
                            if not line:
                                continue
                                
                            # Check if this is a heavy operation that should disable cancel button
                            if not cancel_button_disabled and self.is_heavy_operation(line) and cancel_button:
                                GLib.idle_add(lambda: cancel_button.set_sensitive(False))
                                GLib.idle_add(lambda: cancel_button.set_tooltip_text("Update is processing critical operations and cannot be cancelled"))
                                GLib.idle_add(lambda: self.update_terminal(terminal_view, "\nUpdate is processing critical operations and cannot be cancelled\n"))
                                cancel_button_disabled = True

                            # Update current line and calculate progress
                            current_line += 1
                            # Ensure we don't exceed our total for any reason
                            current_line = min(current_line, total_lines)
                            
                            # Calculate current progress
                            # For heavy operations, show gradual progress instead of jumping
                            if self.is_heavy_operation(line):
                                # Start progress from current point
                                current_progress = base_progress + (current_line - 1) * line_progress_weight
                                # End progress is what it would be after this operation
                                next_progress = base_progress + current_line * line_progress_weight
                                # Cap at 90%
                                next_progress = min(0.9, next_progress)
                                
                                # Update terminal immediately
                                GLib.idle_add(lambda l=line: self.update_terminal(terminal_view, l + "\n"))
                                
                                # Gradually update progress for this heavy operation (5-8 seconds based on operation)
                                duration = 5.0  # Base duration for heavy ops
                                if "download_file" in line.lower() or "aria2c" in line.lower() or "wget" in line.lower():
                                    duration = 8.0  # Longer for downloads
                                elif "extract" in line.lower() or "tar" in line.lower() or "unzip" in line.lower():
                                    duration = 6.0  # Medium for extractions
                                    
                                self.update_progress_gradually(update_progress, current_progress, next_progress, line, duration)
                                
                                # Continue with the next line without updating progress again
                                continue
                            else:
                                # For normal operations, update immediately
                                current_progress = base_progress + (current_line * line_progress_weight)
                                
                                # Cap progress at 90% - the final 10% is reserved for completion tasks
                                current_progress = min(0.9, current_progress)
                                
                                # Update progress
                                GLib.idle_add(update_progress, current_progress, line)
                                
                                # Update terminal
                                GLib.idle_add(lambda l=line: self.update_terminal(terminal_view, l + "\n"))

                        update_process.wait()
                        if update_process.returncode == 0 and not update_cancelled:
                            GLib.idle_add(update_progress, 0.95, "Finalizing update...")
                            
                            # Remove from pending updates
                            if app['folder_name'] in self.pending_updates:
                                del self.pending_updates[app['folder_name']]
                                self.save_pending_updates()
                                print(f"Removed {app['app_name']} from pending updates")
                            
                            time.sleep(0.5)
                            GLib.idle_add(update_progress, 1.0, "Update complete!")
                            time.sleep(1)
                            GLib.idle_add(update_dialog.destroy)
                            
                            # Refresh both the main app list and updates list
                            def refresh_ui():
                                self.load_app_metadata()  # Reload app data
                                if self.updates_button.get_style_context().has_class('selected'):
                                    self.show_update_apps()  # Refresh updates view if we're in it
                                else:
                                    self.show_apps()  # Otherwise refresh main view
                            GLib.idle_add(refresh_ui)
                        else:
                            GLib.idle_add(update_progress, 1.0, "Update failed!")
                            time.sleep(2)
                            GLib.idle_add(update_dialog.destroy)

                    except Exception as e:
                        print(f"Update error: {str(e)}")
                        GLib.idle_add(update_progress, 1.0, f"Error: {str(e)}")
                        time.sleep(2)
                        GLib.idle_add(update_dialog.destroy)
                    
                    finally:
                        if update_process:
                            try:
                                os.killpg(os.getpgid(update_process.pid), signal.SIGTERM)
                            except:
                                pass
                        update_process = None
                        if script_file and os.path.exists(script_file):
                            try:
                                os.remove(script_file)
                                print(f"Cleaned up script: {script_file}")
                            except Exception as e:
                                print(f"Error cleaning up script: {e}")
                                
                # Connect the response signal and cancel button
                thread = threading.Thread(target=update_thread)
                thread.daemon = True
                thread.start()

        except Exception as e:
            print(f"Error in update process: {e}")
            import traceback
            traceback.print_exc()

    def on_update_system(self, button):
        """Handle check for updates button click"""
        print("\n=== Starting Update Check Process ===")
        button.set_sensitive(False)
        button.get_style_context().add_class('updating')
        
        # Set update in progress flag
        self.update_in_progress = True
        
        # Store the current active section when starting the update
        self.update_started_section = "updates"
        
        # Create spinner for version check
        version_check_spinner = Gtk.Spinner()
        version_check_spinner.set_size_request(16, 16)
        version_check_spinner.start()
        
        # Create box for button content
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.pack_start(version_check_spinner, False, False, 0)
        button_box.pack_start(Gtk.Label(label="Checking versions..."), False, False, 0)
        button.remove(button.get_children()[0])  # Remove current label
        button.add(button_box)
        button.show_all()
        
        # Add a timer to continuously check button visibility during update
        self.button_visibility_timer_id = GLib.timeout_add(100, self.ensure_correct_update_button_visibility)
        
        # Ensure correct button visibility
        self.ensure_correct_update_button_visibility()
        
        # Initialize logging for system updates
        self.log_file_path = None
        self.logging_active = False
        self.log_file = None
        
        # Set up automatic logging for system updates
        try:
            # Create a timestamp for the log filename
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            # Create logs directory if it doesn't exist
            log_dir = os.path.expanduser("~/.appstore/logs")
            os.makedirs(log_dir, exist_ok=True)
            # Set up log file path
            self.log_file_path = os.path.join(log_dir, f"system_update_{timestamp}.log")
            self.log_file = open(self.log_file_path, 'w')
            self.logging_active = True
            # Write initial log entry
            self.log_file.write(f"=== System Update Log - {timestamp} ===\n\n")
            self.log_file.flush()
            print(f"Continuous logging started - saving to {self.log_file_path}")
        except Exception as e:
            print(f"Error setting up system update logging: {e}")
            # Reset logging variables if setup fails
            self.log_file_path = None
            self.logging_active = False
            self.log_file = None
        
        def update_progress_safe(progress, label=None):
            def update():
                if label:
                    if "Checking versions" in label:
                        # Keep spinner and label during version check
                        if not isinstance(button.get_child(), Gtk.Box):
                            # Create spinner box if not already present
                            button.remove(button.get_child())
                            spinner = Gtk.Spinner()
                            spinner.set_size_request(16, 16)
                            spinner.start()
                            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                            box.pack_start(spinner, False, False, 0)
                            box.pack_start(Gtk.Label(label=label), False, False, 0)
                            button.add(box)
                            button.show_all()
                        else:
                            # Just update the label text
                            box = button.get_child()
                            box.get_children()[1].set_text(label)
                    else:
                        # For non-version checking states, show progress bar
                        button.remove(button.get_child())
                        button.add(Gtk.Label(label=label))
                        button.show_all()
                        # Only update progress bar when not checking versions
                        self.update_progress(progress)
                
                # Always ensure correct update button visibility
                self.ensure_correct_update_button_visibility()
                
                # Log progress update if logging is active
                if self.logging_active and self.log_file:
                    try:
                        if label:
                            self.log_file.write(f"[Progress {progress}%] {label}\n")
                            self.log_file.flush()
                    except Exception:
                        pass
            
            GLib.idle_add(update)

        def update_system_thread():
            try:
                # Log the start of the update process
                if self.logging_active and self.log_file:
                    self.log_file.write("\n=== Starting System Update Process ===\n")
                    self.log_file.flush()
                
                # Step 1: Update Repository (0-40%)
                print("\n=== Checking Package Manager ===")
                update_progress_safe(0)
                
                cmd = "source /data/data/com.termux/files/usr/bin/termux-setup-package-manager && echo $TERMUX_APP_PACKAGE_MANAGER"
                result = subprocess.run(['bash', '-c', cmd], capture_output=True, text=True)
                pkg_manager = result.stdout.strip()
                print(f"Detected package manager: {pkg_manager}")
                
                # Log package manager info
                if self.logging_active and self.log_file:
                    self.log_file.write(f"Detected package manager: {pkg_manager}\n")
                    self.log_file.flush()

                print("\n=== Updating Repository ===")
                update_progress_safe(10, "Updating repository...")
                
                if pkg_manager == "apt":
                    print("Running apt update...")
                    cmd = "apt update -y"
                    try:
                        process = subprocess.Popen(['bash', '-c', cmd], 
                                                    stdout=subprocess.PIPE, 
                                                    stderr=subprocess.STDOUT,
                                                    universal_newlines=True)
                        # Set a timeout for the command
                        output, _ = process.communicate(timeout=30)  # 30 seconds timeout
                        print(output.strip())
                    except subprocess.TimeoutExpired:
                        process.kill()
                        print("Error: apt update command timed out.")
                    except Exception as e:
                        print(f"Error running apt update: {e}")

                elif pkg_manager == "pacman":
                    print("Running pacman update...")
                    cmd = "pacman -Sy --noconfirm"
                    process = subprocess.Popen(['bash', '-c', cmd], 
                                            stdout=subprocess.PIPE, 
                                            stderr=subprocess.STDOUT,
                                            universal_newlines=True)
                    
                    for line in process.stdout:
                        print(line.strip())
                    process.wait()
                
                # Step 2: Download new app data (40-70%)
                print("\n=== Downloading App Updates ===")
                update_progress_safe(40, "Downloading updates...")
                
                # Load old apps.json data before backing up
                old_json_path = os.path.join(APPSTORE_OLD_JSON_DIR, 'apps.json')
                old_apps_data = []
                if os.path.exists(old_json_path):
                    with open(old_json_path, 'r') as f:
                        old_apps_data = json.load(f)
                
                # Backup old apps.json
                if os.path.exists(APPSTORE_JSON):
                    os.makedirs(APPSTORE_OLD_JSON_DIR, exist_ok=True)
                    shutil.copy2(APPSTORE_JSON, old_json_path)
                    os.remove(APPSTORE_JSON)
                
                # Download new apps.json
                command = f"aria2c -x 16 -s 16 {GITHUB_APPS_JSON} -d {APPSTORE_DIR} -o apps.json"
                subprocess.run(command, shell=True, check=True)
                
                # Load new apps.json data
                with open(APPSTORE_JSON, 'r') as f:
                    new_apps_data = json.load(f)

                # First update versions for native apps
                print("\n=== Getting Native App Versions ===")
                for app in new_apps_data:
                    if (app.get('app_type') == 'native' and 
                        app.get('version') == 'termux_local_version' and 
                        app.get('package_name')):
                        cmd = f"source /data/data/com.termux/files/usr/bin/termux-setup-package-manager && "
                        cmd += f"if [[ \"$TERMUX_APP_PACKAGE_MANAGER\" == \"apt\" ]]; then "
                        cmd += f"apt-cache policy {app['package_name']} | grep 'Candidate:' | awk '{{print $2}}'; "
                        cmd += f"elif [[ \"$TERMUX_APP_PACKAGE_MANAGER\" == \"pacman\" ]]; then "
                        cmd += f"pacman -Si {app['package_name']} 2>/dev/null | grep 'Version' | awk '{{print $3}}'; fi"
                        
                        try:
                            result = subprocess.run(['bash', '-c', cmd], 
                                                 capture_output=True, 
                                                 text=True, 
                                                 timeout=10)
                            if result.returncode == 0 and result.stdout.strip():
                                app['version'] = result.stdout.strip()
                                print(f"Got version for {app['app_name']}: {app['version']}")
                            else:
                                app['version'] = 'Unavailable'
                                print(f"Could not get version for {app['app_name']}, setting to Unavailable")
                        except Exception as e:
                            app['version'] = 'Unavailable'
                            print(f"Error getting version for {app['app_name']}: {e}")

                # Then update versions for distro apps if distro is enabled
                print("\n=== Getting Distro App Versions ===")
                termux_desktop_config = "/data/data/com.termux/files/usr/etc/termux-desktop/configuration.conf"
                distro_enabled = False  # Initialize the variable
                selected_distro = None  # Initialize the variable
                
                if os.path.exists(termux_desktop_config):
                    try:
                        with open(termux_desktop_config, 'r') as f:
                            for line in f:
                                line = line.strip()
                                if line.startswith('distro_add_answer='):
                                    value = line.split('=')[1].strip().strip('"').strip("'").lower()
                                    distro_enabled = value in ['y', 'yes']
                                elif line.startswith('selected_distro='):
                                    selected_distro = line.split('=')[1].strip().strip('"').strip("'").lower()
                    except Exception as e:
                        print(f"Error reading Termux Desktop config: {e}")
                        return  # Exit the method if there's an error

                # Debugging output
                print(f"distro_enabled: {distro_enabled}, selected_distro: {selected_distro}")

                if distro_enabled and selected_distro:
                    # First check if proot-distro is working correctly
                    test_cmd = f"proot-distro login {selected_distro} --shared-tmp -- /bin/bash -c 'echo test'"
                    try:
                        test_result = subprocess.run(['bash', '-c', test_cmd],
                                                  capture_output=True,
                                                  text=True,
                                                  timeout=10)
                        if test_result.returncode == 0:
                            print(f"proot-distro test successful for {selected_distro}")
                            
                            for app in new_apps_data:
                                if (app.get('app_type') == 'distro' and 
                                    app.get('version') == 'distro_local_version'):
                                    
                                    supported_distro = app.get('supported_distro')
                                    if supported_distro and supported_distro != 'all':
                                        supported_distros = [d.strip().lower() for d in supported_distro.split(',')]
                                        if selected_distro not in supported_distros:
                                            print(f"Skipping {app['app_name']}: not compatible with {selected_distro}")
                                            continue

                                    package_name = app.get(f"{selected_distro}_package_name")
                                    if not package_name:
                                        package_name = app.get('package_name')
                                    
                                    if not package_name:
                                        print(f"Skipping {app['app_name']}: no package name found")
                                        continue

                                    print(f"Getting version for {app['app_name']}...")
                                    cmd = f"proot-distro login {selected_distro} --shared-tmp -- /bin/bash -c "
                                    
                                    if selected_distro in ['ubuntu', 'debian']:
                                        cmd += f"'apt-cache policy {package_name} | grep Candidate: | awk \"{{print \\$2}}\"'"
                                    elif selected_distro == 'fedora':
                                        cmd += f"'dnf info {package_name} 2>/dev/null | awk -F: \"/Version/ {{print \\$2}}\" | tr -d \" \"'"
                                    elif selected_distro == 'archlinux':
                                        cmd += f"'pacman -Si {package_name} 2>/dev/null | grep Version | awk \"{{print \\$3}}\"'"

                                    try:
                                        result = subprocess.run(['bash', '-c', cmd], 
                                                             capture_output=True, 
                                                             text=True, 
                                                             timeout=30)
                                        if result.returncode == 0 and result.stdout.strip():
                                            app['version'] = result.stdout.strip()
                                            print(f"Got version for {app['app_name']}: {app['version']}")
                                        else:
                                            app['version'] = 'Unavailable'
                                            print(f"Could not get version for {app['app_name']}, setting to Unavailable")
                                    except Exception as e:
                                        app['version'] = 'Unavailable'
                                        print(f"Error getting version for {app['app_name']}: {e}")
                        else:
                            print(f"proot-distro test failed for {selected_distro}")
                            print(f"Error: {test_result.stderr}")
                    except Exception as e:
                        print(f"Error testing proot-distro: {e}")

                # Save updated versions to new apps.json
                print("\n=== Saving Updated App Data ===")
                print("Saving updated versions to apps.json...")
                with open(APPSTORE_JSON, 'w') as f:
                    json.dump(new_apps_data, f, indent=2)
                print("Successfully saved updated app data")

                # Now compare versions and update pending_updates
                print("\n=== Comparing Versions ===")
                for app in new_apps_data:
                    print(f"\nChecking app: {app['app_name']}")
                    print(f"Is installed? {app['folder_name'] in self.installed_apps}")
                    
                    if app['folder_name'] in self.installed_apps:  # Only check installed apps
                        old_app = next((a for a in old_apps_data if a['folder_name'] == app['folder_name']), None)
                        print(f"Found old app data? {old_app is not None}")
                        
                        if old_app:
                            old_version = old_app.get('version')
                            new_version = app.get('version')
                            print(f"Old version: {old_version}")
                            print(f"New version: {new_version}")
                            
                            # Skip comparison if either version is unavailable
                            if old_version in ['termux_local_version', 'distro_local_version', 'Unavailable'] or \
                               new_version in ['termux_local_version', 'distro_local_version', 'Unavailable']:
                                print(f"Skipping {app['app_name']}: version unavailable")
                                continue
                                
                            if old_version != new_version:
                                print(f"Update found for {app['app_name']}: {old_version} -> {new_version}")
                                self.pending_updates[app['folder_name']] = new_version
                                print(f"Added to pending updates. Current updates: {self.pending_updates}")
                            else:
                                print(f"No update needed - versions match")
                
                # Save pending updates
                print("\n=== Saving Updates ===")
                print(f"Final pending updates: {self.pending_updates}")
                self.save_pending_updates()
                
                # Step 3: Update logos (70-90%)
                print("\n=== Updating App Logos ===")
                update_progress_safe(70, "Updating app logos...")
                
                if os.path.exists(APPSTORE_LOGO_DIR):
                    shutil.rmtree(APPSTORE_LOGO_DIR)
                self.download_and_extract_logos()
                
                # Step 4: Load new data and check for updates (90-100%)
                print("\n=== Processing Updates ===")
                update_progress_safe(90, "Checking versions...")  # Keep spinner during version checks
                
                # Load new app data and check for updates
                self.load_app_metadata()
                
                print("\n=== Update Check Complete ===")
                update_progress_safe(100, "Check for Updates")
                
                # Log update completion
                if self.logging_active and self.log_file:
                    self.log_file.write("\n=== System Update Process Completed Successfully ===\n")
                    self.log_file.flush()
                
                # Reset button and refresh display
                GLib.idle_add(self.update_complete)
                
                # Reload all app data first
                GLib.idle_add(self.load_app_metadata)
                
                # Then refresh the current view
                def refresh_update_view():
                    # Get current active section by checking which button is selected
                    current_section = None
                    if self.explore_button.get_style_context().has_class('selected'):
                        current_section = "explore"
                    elif self.installed_button.get_style_context().has_class('selected'):
                        current_section = "installed"
                    elif self.updates_button.get_style_context().has_class('selected'):
                        current_section = "updates"
                    
                    # Clear current content to prevent flashing old content
                    self.clear_app_list_box()
                    
                    # Add loading indicator
                    loading_box = self.show_temporary_loading()
                    
                    # Apply the correct UI state for the current tab
                    if current_section == "explore":
                        self.sidebar.show()
                        self.update_button.hide()
                        
                        # Load content on next idle
                        def load_content():
                            self.clear_app_list_box()
                            self.show_apps(selected_category)
                            return False
                            
                        GLib.idle_add(load_content)
                        
                    elif current_section == "installed":
                        self.sidebar.hide()
                        self.update_button.hide()
                        
                        # Load content on next idle
                        def load_content():
                            self.clear_app_list_box()
                            self.show_installed_apps()
                            return False
                            
                        GLib.idle_add(load_content)
                        
                    elif current_section == "updates":
                        self.sidebar.hide()
                        self.update_button.show()
                        
                        # Load content on next idle
                        def load_content():
                            self.clear_app_list_box()
                            self.show_update_apps()
                            return False
                            
                        GLib.idle_add(load_content)
                
                GLib.idle_add(refresh_update_view)
                
            except Exception as e:
                print(f"\n=== Update Check Failed ===")
                print(f"Error: {str(e)}")
                print(f"Stack trace:")
                import traceback
                traceback.print_exc()
                
                # Log error information
                if self.logging_active and self.log_file:
                    try:
                        self.log_file.write(f"\n=== System Update Process Failed ===\n")
                        self.log_file.write(f"Error: {str(e)}\n")
                        self.log_file.write("Stack trace:\n")
                        traceback.print_exc(file=self.log_file)
                        self.log_file.flush()
                    except Exception:
                        pass
                
                # Reset update state on error
                GLib.idle_add(lambda: setattr(self, 'update_in_progress', False))
                
                # Remove visibility timer on error
                if hasattr(self, 'button_visibility_timer_id'):
                    GLib.idle_add(lambda: GLib.source_remove(self.button_visibility_timer_id))
                    GLib.idle_add(lambda: setattr(self, 'button_visibility_timer_id', None))
                
                GLib.idle_add(lambda: self.show_error_dialog(f"Update check failed: {str(e)}"))
                GLib.idle_add(self.update_complete)

        # Submit the update task to the thread pool
        self.thread_pool.submit(update_system_thread)

    def update_progress(self, progress):
        """Update the progress bar effect on button"""
        # Mark the button as updating
        self.update_button.get_style_context().add_class('updating')
        
        # Remove any existing progress classes
        for i in range(10, 101, 10):
            self.update_button.get_style_context().remove_class(f'progress-{i}')
        
        # Round progress to nearest 10%
        if progress > 0:
            progress_rounded = int(round(progress / 10.0)) * 10
            progress_rounded = max(10, min(100, progress_rounded))  # Ensure between 10-100
            
            # Add the appropriate progress class
            self.update_button.get_style_context().add_class(f'progress-{progress_rounded}')
            
            # Update the button label
            self.update_button.set_label(f"Updating... {progress}%")
        
        # Keep the UI responsive
        while Gtk.events_pending():
            Gtk.main_iteration()
            
        return True

    def update_complete(self):
        """Reset update button state after update completes"""
        # Close log file if continuous logging is active
        if self.logging_active and self.log_file:
            try:
                self.log_file.write("\n--- Update completed successfully ---\n")
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None
            self.logging_active = False
            self.log_file_path = None
            
        self.update_button.set_sensitive(True)
        self.update_button.set_label("Check for Updates")
        self.update_button.get_style_context().remove_class('updating')
        
        # Remove all progress classes
        for i in range(10, 101, 10):
            self.update_button.get_style_context().remove_class(f'progress-{i}')
        
        # Reset update state
        self.update_in_progress = False
        
        # Remove the visibility check timer
        if hasattr(self, 'button_visibility_timer_id'):
            GLib.source_remove(self.button_visibility_timer_id)
            self.button_visibility_timer_id = None
        
        # Ensure update button is only visible on updates tab
        if not (self.updates_button.get_style_context().has_class('selected') or
                self.updates_button.get_style_context().has_class('active')):
            self.update_button.hide()
        
        return False

    def on_section_clicked(self, button, section):
        """Handle section button clicks"""
        try:
            # Store current section for later reference
            self.current_section = section
            
            # Update button states - keep both classes for compatibility
            for btn in [self.explore_button, self.installed_button, self.updates_button]:
                if btn:  # Safety check
                    btn.get_style_context().remove_class('selected')
                    btn.get_style_context().remove_class('active')
            
            # Add both classes to clicked button for proper highlighting
            if button:  # Safety check
                button.get_style_context().add_class('selected')
                button.get_style_context().add_class('active')
            
            # Hide search box when changing tabs
            if hasattr(self, 'search_box') and hasattr(self, 'search_button'):
                self.search_box.hide()
                self.search_button.set_image(Gtk.Image.new_from_icon_name("system-search-symbolic", Gtk.IconSize.BUTTON))
                self.search_button.set_tooltip_text("Show Search")
            
            # Safety check for UI initialization
            if not hasattr(self, 'search_entry') or not hasattr(self, 'app_list_box'):
                print("Warning: UI not fully initialized yet, deferring section display")
                # Schedule another attempt after a short delay
                GLib.timeout_add(100, lambda: self.on_section_clicked(button, section))
                return
                
            # Clear search entry
            if hasattr(self, 'search_entry'):
                self.search_entry.set_text("")
            
            # Clear current content immediately to prevent brief display of previous content
            if hasattr(self, 'app_list_box'):
                self.clear_app_list_box()
                
                # Add temporary loading indicator
                loading_box = self.show_temporary_loading()
            
            # Show/hide UI elements based on section
            if section == "explore":
                # Show categories, hide update button
                if hasattr(self, 'sidebar'):
                    self.sidebar.show()
                if hasattr(self, 'update_button'):
                    self.update_button.hide()
                if hasattr(self, 'search_entry'):
                    self.search_entry.show()
                
                # Get the currently selected category
                selected_category = None
                if hasattr(self, 'category_buttons'):
                    for cat_button in self.category_buttons:
                        if cat_button.get_style_context().has_class('selected'):
                            selected_category = cat_button.get_label()
                            break
                
                if selected_category == "All Apps" or selected_category is None:
                    selected_category = None
                
                # Define function to load content and remove spinner
                def load_explore_content():
                    if hasattr(self, 'app_list_box'):
                        self.clear_app_list_box()  # Clear loading indicator
                        self.show_apps(selected_category)
                    return False
                
                # Schedule content load on next idle
                GLib.idle_add(load_explore_content)
                
            elif section == "installed":
                # Hide categories and update button
                if hasattr(self, 'sidebar'):
                    self.sidebar.hide()
                if hasattr(self, 'update_button'):
                    self.update_button.hide()
                if hasattr(self, 'search_entry'):
                    self.search_entry.show()
                
                # Define function to load content and remove spinner
                def load_installed_content():
                    if hasattr(self, 'app_list_box'):
                        self.clear_app_list_box()  # Clear loading indicator
                        self.show_installed_apps()
                    return False
                
                # Schedule content load on next idle
                GLib.idle_add(load_installed_content)
                
            else:  # updates
                # Hide categories, show update button
                if hasattr(self, 'sidebar'):
                    self.sidebar.hide()
                if hasattr(self, 'update_button'):
                    self.update_button.show()
                if hasattr(self, 'search_entry'):
                    self.search_entry.show()
                
                # Define function to load content and remove spinner
                def load_updates_content():
                    if hasattr(self, 'app_list_box'):
                        self.clear_app_list_box()  # Clear loading indicator
                        self.show_update_apps()
                    return False
                
                # Schedule content load on next idle
                GLib.idle_add(load_updates_content)
                
        except Exception as e:
            print(f"Error in on_section_clicked: {e}")
            import traceback
            traceback.print_exc()

    def show_installed_apps(self):
        """Display installed apps"""
        try:
            # Clear current list safely
            GLib.idle_add(self.clear_app_list_box)

            # Get search text
            search_text = self.search_entry.get_text().lower()
            
            # Collect all installed apps
            all_installed_apps = [app for app in self.apps_data if app['folder_name'] in self.installed_apps]
            
            # If search text is provided, filter the apps
            if search_text:
                if self.get_setting("enable_fuzzy_search", False) and (fuzz is not None):
                    # Use fuzzy search
                    fuzzy_threshold = 60  # Minimum score to consider a match
                    fuzzy_matches = []
                    
                    for app in all_installed_apps:
                        # Check app name
                        name_score = fuzz.partial_ratio(search_text, app['app_name'].lower())
                        
                        # Check description
                        desc_score = fuzz.partial_ratio(search_text, app['description'].lower())
                        
                        # Check categories
                        cat_score = 0
                        for cat in app['categories']:
                            cat_score = max(cat_score, fuzz.partial_ratio(search_text, cat.lower()))
                        
                        # Use the best score
                        max_score = max(name_score, desc_score, cat_score)
                        
                        if max_score >= fuzzy_threshold:
                            # Store the app and its score for sorting
                            fuzzy_matches.append((app, max_score))
                    
                    # Sort by score (highest first) and extract just the apps
                    fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
                    filtered_apps = [app for app, score in fuzzy_matches]
                else:
                    # Use regular search
                    filtered_apps = [
                        app for app in all_installed_apps
                        if search_text in app['app_name'].lower() or 
                        search_text in app['description'].lower() or 
                        any(search_text in cat.lower() for cat in app['categories'])
                    ]
            else:
                filtered_apps = all_installed_apps

            # If no apps found, show a message
            if not filtered_apps:
                if search_text:
                    # Show the regular no search results message
                    GLib.idle_add(self._show_no_apps_message, search_text)
                else:
                    # Show a specific "no installed apps" message
                    GLib.idle_add(self._show_no_installed_apps_message)
            else:
                # Display the filtered apps
                for app in filtered_apps:
                    GLib.idle_add(lambda a=app: self.add_app_card(a))

            GLib.idle_add(self.app_list_box.show_all)
        except Exception as e:
            print(f"Error in show_installed_apps: {e}")
            import traceback
            traceback.print_exc()
            
    def _show_no_installed_apps_message(self):
        """Show a message when no apps are installed"""
        message_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        message_box.set_valign(Gtk.Align.CENTER)
        message_box.set_halign(Gtk.Align.CENTER)
        
        # Add an icon
        icon = Gtk.Image.new_from_icon_name("system-software-install", Gtk.IconSize.DIALOG)
        message_box.pack_start(icon, False, False, 0)
        
        # Add message
        message = Gtk.Label()
        message.set_markup("<span size='larger'>No Applications Installed</span>")
        message_box.pack_start(message, False, False, 0)
        
        # Add suggestion
        suggestion = Gtk.Label()
        suggestion.set_markup("<span>Go to the Explore tab to install applications</span>")
        message_box.pack_start(suggestion, False, False, 10)
        
        self.app_list_box.pack_start(message_box, True, True, 0)

    def show_update_apps(self):
        """Display apps that have updates available"""
        try:
            # Clear current list safely
            GLib.idle_add(self.clear_app_list_box)

            # Get search text
            search_text = self.search_entry.get_text().lower()
            
            # Collect all apps with updates
            all_update_apps = [app for app in self.apps_data if app['folder_name'] in self.pending_updates]
            
            # If search text is provided, filter the apps
            if search_text:
                if self.get_setting("enable_fuzzy_search", False) and (fuzz is not None):
                    # Use fuzzy search
                    fuzzy_threshold = 60  # Minimum score to consider a match
                    fuzzy_matches = []
                    
                    for app in all_update_apps:
                        # Check app name
                        name_score = fuzz.partial_ratio(search_text, app['app_name'].lower())
                        
                        # Check description
                        desc_score = fuzz.partial_ratio(search_text, app['description'].lower())
                        
                        # Check categories
                        cat_score = 0
                        for cat in app['categories']:
                            cat_score = max(cat_score, fuzz.partial_ratio(search_text, cat.lower()))
                        
                        # Use the best score
                        max_score = max(name_score, desc_score, cat_score)
                        
                        if max_score >= fuzzy_threshold:
                            # Store the app and its score for sorting
                            fuzzy_matches.append((app, max_score))
                    
                    # Sort by score (highest first) and extract just the apps
                    fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
                    filtered_apps = [app for app, score in fuzzy_matches]
                else:
                    # Use regular search
                    filtered_apps = [
                        app for app in all_update_apps
                        if search_text in app['app_name'].lower() or 
                        search_text in app['description'].lower() or 
                        any(search_text in cat.lower() for cat in app['categories'])
                    ]
            else:
                filtered_apps = all_update_apps

            # If no updates found, show a message
            if not filtered_apps:
                if search_text:
                    # Show the regular no search results message
                    GLib.idle_add(self._show_no_apps_message, search_text)
                else:
                    # Show a specific "no updates available" message
                    GLib.idle_add(self._show_no_updates_message)
            else:
                # Display the filtered apps
                for app in filtered_apps:
                    GLib.idle_add(lambda a=app: self.add_app_card(a))

            GLib.idle_add(self.app_list_box.show_all)
        except Exception as e:
            print(f"Error in show_update_apps: {e}")
            import traceback
            traceback.print_exc()
            
    def _show_no_updates_message(self):
        """Show a message when no updates are available"""
        message_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        message_box.set_valign(Gtk.Align.CENTER)
        message_box.set_halign(Gtk.Align.CENTER)
        
        # Add an icon
        icon = Gtk.Image.new_from_icon_name("software-update-available", Gtk.IconSize.DIALOG)
        message_box.pack_start(icon, False, False, 0)
        
        # Add message
        message = Gtk.Label()
        message.set_markup("<span size='larger'>No Updates Available</span>")
        message_box.pack_start(message, False, False, 0)
        
        # Add suggestion
        suggestion = Gtk.Label()
        suggestion.set_markup("<span>All your applications are up to date</span>")
        message_box.pack_start(suggestion, False, False, 10)
        
        self.app_list_box.pack_start(message_box, True, True, 0)

    def process_ui_updates(self):
        """Process UI updates in a separate thread"""
        while True:
            try:
                update_func = self.ui_update_queue.get()
                if update_func is None:  # Shutdown signal
                    break
                GLib.idle_add(update_func)
                self.ui_update_queue.task_done()
            except Exception as e:
                print(f"Error processing UI update: {e}")
                continue

    def process_pending_ui_updates(self):
        """Process any pending UI updates"""
        try:
            while True:
                update_func = self.ui_update_queue.get_nowait()
                if update_func is not None:
                    GLib.idle_add(update_func)
                self.ui_update_queue.task_done()
        except queue.Empty:
            pass
        return True  # Keep the timer active

    def queue_ui_update(self, update_func):
        """Queue a UI update to be processed"""
        self.ui_update_queue.put(update_func)

    def cleanup_installation_state(self):
        """Clean up installation state and UI"""
        self.installation_cancelled = False
        self.current_installation = None
        self.hide_loading_indicators()
        
        # Only refresh UI if not in the middle of cancellation
        # This prevents double UI refreshes when cancelling
        if not hasattr(self, 'cancellation_in_progress') or not self.cancellation_in_progress:
            GLib.idle_add(self.refresh_complete)
            
            # Use a small delay for showing apps to ensure proper UI state
            if hasattr(self, 'current_section') and self.current_section == "explore":
                # Keep the same category selection
                GLib.timeout_add(100, lambda: self.show_apps(self._get_selected_category()))
            elif hasattr(self, 'current_section'):
                # Handle other sections
                if self.current_section == "installed":
                    GLib.timeout_add(100, self.show_installed_apps)
                elif self.current_section == "updates":
                    GLib.timeout_add(100, self.show_update_apps)
        else:
            # If cancellation is in progress, we only need to refresh the current view
            # without rebuilding the entire UI
            GLib.timeout_add(100, lambda: self._refresh_current_view())
    
    def _get_selected_category(self):
        """Helper to get the currently selected category"""
        if hasattr(self, 'category_buttons'):
            for cat_button in self.category_buttons:
                if cat_button.get_style_context().has_class('selected'):
                    category = cat_button.get_label()
                    return None if category == "All Apps" else category
        return None

    def update_terminal(self, terminal_view, text):
        """Update the terminal view with new text and append to log file if logging is active"""
        if not text:
            return
        
        # Initialize logging attributes if they don't exist
        if not hasattr(self, 'logging_active'):
            self.logging_active = False
            self.log_file = None
            self.log_file_path = None
        
        # Create a terminal emulator for the text view if it doesn't exist yet
        if not hasattr(terminal_view, 'terminal_emulator'):
            terminal_view.terminal_emulator = TerminalEmulator(terminal_view)
        
        # Process and append the text
        terminal_view.terminal_emulator.append_text(text)
        
        # Append to log file if continuous logging is active
        if self.logging_active and self.log_file:
            try:
                # Strip ANSI codes when writing to log file
                clean_text = AnsiColorParser().strip_ansi(text)
                
                # Write to log file, ensuring a newline is added if needed
                if self.log_file.tell() > 0:
                    # Move to the position before the last character
                    self.log_file.seek(self.log_file.tell() - 1, 0)
                    last_char = self.log_file.read(1)
                    self.log_file.seek(0, 2)  # Move back to the end
                    
                    # If the last character isn't a newline and the new text doesn't start with one,
                    # add a newline before writing
                    if last_char != '\n' and not clean_text.startswith('\n'):
                        self.log_file.write('\n')
                        
                self.log_file.write(clean_text)
                self.log_file.flush()  # Ensure it's written immediately
            except Exception:
                # If there's an error writing to the log file, disable logging
                try:
                    self.log_file.close()
                except Exception:
                    pass
                self.log_file = None
                self.logging_active = False
                self.log_file_path = None
        
        return False

    def create_progress_dialog(self, title="Installing...", allow_cancel=True):
        # Create dialog
        dialog = Gtk.Dialog(
            title=title,
            transient_for=self,
            modal=True,
            destroy_with_parent=True
        )
        dialog.get_style_context().add_class("progress-dialog")
        dialog.set_default_size(450, 250)
        # Allow resizing again
        dialog.set_resizable(True)
        dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        
        # Initialize logging variables
        self.logging_active = False
        self.log_file = None
        self.log_file_path = None

        # Set the right action button - Cancel
        cancel_button = None
        if allow_cancel:
            cancel_button = dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
            cancel_button.get_style_context().add_class("cancel-button")
            # Store the cancel button as a property on the dialog for later access
            dialog.cancel_button = cancel_button
        
        # Create container box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.set_margin_top(10)
        content_box.set_margin_bottom(10)
        content_box.set_margin_start(15)
        content_box.set_margin_end(15)
        
        # Create stack for progress view and terminal view
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        stack.set_transition_duration(300)
        
        # Create progress view box
        progress_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        progress_view.get_style_context().add_class("progress-view")
        
        # Create status label
        status_label = Gtk.Label(label="Initializing...")
        status_label.set_line_wrap(True)
        status_label.set_line_wrap_mode(Gtk.WrapMode.WORD_CHAR)  # Better word wrapping
        status_label.set_xalign(0)
        status_label.set_max_width_chars(40)  # Limit width to force wrapping
        status_label.set_ellipsize(Pango.EllipsizeMode.END)  # Add ellipsis for very long lines
        status_label.get_style_context().add_class("status-label")
        
        # Create progress bar
        progress_bar = Gtk.ProgressBar()
        progress_bar.set_show_text(True)
        progress_bar.set_text("0%")
        progress_bar.set_fraction(0.0)
        
        # Create terminal view
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_propagate_natural_height(True)  # Allow content to expand naturally
        scrolled_window.set_min_content_height(100)
        # Remove max height restriction to allow resizing
        #scrolled_window.set_max_content_height(150)
                
        # Create TextView for terminal output
        text_view = Gtk.TextView()
        text_view.get_style_context().add_class("terminal-view")
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_monospace(True)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)  # Enable text wrapping in terminal
        # Set font size
        font_desc = Pango.FontDescription()
        font_desc.set_size(10 * Pango.SCALE)
        text_view.override_font(font_desc)
        
        # Set terminal colors
        self.text_view = text_view
        self.text_view.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 1))
        self.text_view.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(1, 1, 1, 1))
        
        scrolled_window.add(text_view)
        
        # Add a box for terminal controls
        terminal_controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        terminal_controls_box.set_halign(Gtk.Align.END)
        
        # Add toggle terminal button and save log button
        toggle_terminal_button = Gtk.Button()
        toggle_terminal_button.set_label("View Terminal ▾")
        toggle_terminal_button.get_style_context().add_class("terminal-toggle-button")
        
        # Add save log button
        save_log_button = Gtk.Button()
        save_log_button.set_label("Save Log")
        save_log_button.get_style_context().add_class("terminal-toggle-button")
        
        terminal_controls_box.pack_end(toggle_terminal_button, False, False, 0)
        terminal_controls_box.pack_end(save_log_button, False, False, 0)
        
        # Add widgets to progress view
        progress_view.pack_start(status_label, False, False, 0)
        progress_view.pack_start(progress_bar, False, False, 0)
        progress_view.pack_start(terminal_controls_box, False, False, 0)
        
        # Create terminal view box
        terminal_view_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # Create back to progress button
        back_to_progress_button = Gtk.Button()
        back_to_progress_button.set_label("View Progress ▴")
        back_to_progress_button.get_style_context().add_class("terminal-toggle-button")
        back_to_progress_button.set_halign(Gtk.Align.END)
        
        # Add widgets to terminal view
        terminal_view_box.pack_start(scrolled_window, True, True, 0)
        terminal_view_box.pack_end(back_to_progress_button, False, False, 0)
        
        # Add views to stack
        stack.add_named(progress_view, "progress")
        stack.add_named(terminal_view_box, "terminal")
        stack.set_visible_child_name("progress")
        
        # Add stack to content box
        content_box.pack_start(stack, True, True, 0)
        
        # Add content box to dialog
        dialog_content_area = dialog.get_content_area()
        dialog_content_area.add(content_box)
        
        # Show all widgets
        dialog.show_all()
        
        # Set up the toggle terminal button
        def toggle_terminal(button):
            current_child = stack.get_visible_child_name()
            if current_child == "progress":
                stack.set_visible_child_name("terminal")
                button.set_label("View Progress ▴")
            else:
                stack.set_visible_child_name("progress")
                button.set_label("View Terminal ▾")
        
        toggle_terminal_button.connect("clicked", toggle_terminal)
        back_to_progress_button.connect("clicked", toggle_terminal)
        
        # Handle dialog response (close/cancel)
        def on_dialog_response(dialog, response_id):
            # Close log file if logging is active
            if hasattr(self, 'logging_active') and self.logging_active and self.log_file:
                try:
                    self.log_file.write("\n--- Log closed by user ---\n")
                    self.log_file.close()
                except:
                    pass
                self.log_file = None
                self.logging_active = False
                self.log_file_path = None
        
        dialog.connect("response", on_dialog_response)
        
        # Handle log saving
        def on_save_log_clicked(button):
            # If logging is already active, stop it
            if hasattr(self, 'logging_active') and self.logging_active and self.log_file:
                try:
                    self.log_file.write("\n--- Log saved by user ---\n")
                    self.log_file.close()
                except:
                    pass
            
            # Get text from buffer
            buffer = text_view.get_buffer()
            start_iter = buffer.get_start_iter()
            end_iter = buffer.get_end_iter()
            log_text = buffer.get_text(start_iter, end_iter, False)
            
            if not log_text.strip():
                return  # No text to save
            
            # Create file chooser dialog
            file_chooser = Gtk.FileChooserDialog(
                title="Save Log",
                parent=dialog,
                action=Gtk.FileChooserAction.SAVE
            )
            file_chooser.add_button("Cancel", Gtk.ResponseType.CANCEL)
            file_chooser.add_button("Save", Gtk.ResponseType.OK)
            file_chooser.set_do_overwrite_confirmation(True)
            
            # Set default filename
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            file_chooser.set_current_name(f"appstore-log-{timestamp}.txt")
            
            # Set default folder to HOME
            file_chooser.set_current_folder(os.path.expanduser("~"))
            
            # Run dialog
            response = file_chooser.run()
            
            if response == Gtk.ResponseType.OK:
                filename = file_chooser.get_filename()
                try:
                    with open(filename, 'w') as f:
                        f.write(log_text)
                    
                    # Show confirmation
                    print(f"Log saved to {filename}")
                    
                    # Display a simple notification
                    notification = Gtk.MessageDialog(
                        transient_for=file_chooser,
                        message_type=Gtk.MessageType.INFO,
                        buttons=Gtk.ButtonsType.OK,
                        text=f"Log saved to {filename}"
                    )
                    notification.run()
                    notification.destroy()
                    
                except Exception as e:
                    # Show error
                    error_dialog = Gtk.MessageDialog(
                        transient_for=file_chooser,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        text=f"Error saving log: {e}"
                    )
                    error_dialog.run()
                    error_dialog.destroy()
            
            file_chooser.destroy()
        
        save_log_button.connect("clicked", on_save_log_clicked)
        
        # Initialize the terminal emulator for syntax highlighting
        terminal_emulator = TerminalEmulator(text_view)
        
        return dialog, status_label, progress_bar, text_view

    def ensure_correct_update_button_visibility(self):
        """Ensure update button is only visible on updates tab"""
        # Check for either 'selected' or 'active' class for compatibility
        if (self.updates_button.get_style_context().has_class('selected') or 
            self.updates_button.get_style_context().has_class('active')):
            self.update_button.show()
        else:
            self.update_button.hide()
        return self.update_in_progress  # Keep timer running if update is in progress

    def show_temporary_loading(self):
        """Show a temporary loading spinner in the app list box"""
        # Safety check - if app_list_box doesn't exist yet, just return
        if not hasattr(self, 'app_list_box'):
            print("Warning: app_list_box not initialized yet in show_temporary_loading")
            return None
            
        try:
            # Create a centered box for the spinner
            loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            loading_box.set_valign(Gtk.Align.CENTER)
            loading_box.set_halign(Gtk.Align.CENTER)
            
            # Create and start spinner
            spinner = Gtk.Spinner()
            spinner.set_size_request(32, 32)
            spinner.start()
            loading_box.pack_start(spinner, False, False, 0)
            
            # Add loading label
            label = Gtk.Label(label="Loading...")
            loading_box.pack_start(label, False, False, 0)
            
            # Add to app list box
            self.app_list_box.pack_start(loading_box, True, True, 0)
            loading_box.show_all()
            
            return loading_box
        except Exception as e:
            print(f"Error in show_temporary_loading: {e}")
            return None

    def load_explore_content(self):
        """Load content for the explore section"""
        self.clear_app_list_box()  # Clear loading indicator
        self.show_apps()
        return False
    
    def load_installed_content(self):
        """Load content for the installed section"""
        self.clear_app_list_box()  # Clear loading indicator
        self.show_installed_apps()
        return False
    
    def load_updates_content(self):
        """Load content for the updates section"""
        self.clear_app_list_box()  # Clear loading indicator
        self.show_update_apps()
        return False

    def migrate_old_data(self):
        """Migrate data from old .termux_appstore directory to new .appstore directory"""
        try:
            old_dir = os.path.expanduser("~/.termux_appstore")
            if os.path.exists(old_dir):
                print(f"Found old data directory: {old_dir}, migrating data...")
                
                # Migrate installed apps data
                old_installed_apps = os.path.join(old_dir, "installed_apps.json")
                if os.path.exists(old_installed_apps):
                    print(f"Migrating installed apps data from {old_installed_apps} to {INSTALLED_APPS_FILE}")
                    shutil.copy2(old_installed_apps, INSTALLED_APPS_FILE)
                
                # Migrate updates tracking data
                old_updates = os.path.join(old_dir, "updates.json")
                if os.path.exists(old_updates):
                    print(f"Migrating updates data from {old_updates} to {UPDATES_TRACKING_FILE}")
                    shutil.copy2(old_updates, UPDATES_TRACKING_FILE)
                
                # Migrate last version check data
                old_version_check = os.path.join(old_dir, "last_version_check")
                if os.path.exists(old_version_check):
                    print(f"Migrating version check data from {old_version_check} to {LAST_VERSION_CHECK_FILE}")
                    shutil.copy2(old_version_check, LAST_VERSION_CHECK_FILE)
                
                # Migrate settings if they exist
                old_settings = os.path.join(old_dir, "settings.json")
                if os.path.exists(old_settings):
                    print(f"Migrating settings from {old_settings} to {SETTINGS_FILE}")
                    shutil.copy2(old_settings, SETTINGS_FILE)
                
                print("Migration completed successfully.")
                
                # Remove the old directory without creating a backup
                print(f"Removing old data directory: {old_dir}")
                try:
                    shutil.rmtree(old_dir)
                except Exception as rm_error:
                    print(f"Warning: Could not remove old directory: {rm_error}")
                    print("You may want to manually remove it later.")
            else:
                print("No old data directory found, nothing to migrate.")
        except Exception as e:
            print(f"Error during data migration: {e}")
            import traceback
            traceback.print_exc()

    def load_settings(self):
        """Load user settings from settings.json"""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    self.settings = json.load(f)
                    # Add any keys that might be missing in old settings files
                    if "use_terminal_for_progress" not in self.settings:
                        self.settings["use_terminal_for_progress"] = False
                    if "enable_auto_refresh" not in self.settings:
                        self.settings["enable_auto_refresh"] = True
                    if "last_category" not in self.settings:
                        self.settings["last_category"] = "All Apps"
                    if "show_command_output" not in self.settings:
                        self.settings["show_command_output"] = False
                    if "enable_fuzzy_search" not in self.settings:
                        self.settings["enable_fuzzy_search"] = False
                    # Save the updated settings
                    self.save_settings()
            else:
                # Create default settings
                self.settings = {
                    "use_terminal_for_progress": False,
                    "enable_auto_refresh": True,
                    "last_category": "All Apps",
                    "show_command_output": False,
                    "enable_fuzzy_search": False
                    # Add more default settings as needed
                }
                # Save default settings
                self.save_settings()
                print("Created default settings")
        except Exception as e:
            print(f"Error loading settings: {e}")
            # Fallback to default settings
            self.settings = {
                "use_terminal_for_progress": False,
                "enable_auto_refresh": True,
                "last_category": "All Apps",
                "show_command_output": False,
                "enable_fuzzy_search": False
            }
    
    def save_settings(self):
        """Save user settings to settings.json"""
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self.settings, f, indent=2)
                print(f"Settings saved: {self.settings}")
        except Exception as e:
            print(f"Error saving settings: {e}")
            
    def get_setting(self, key, default=None):
        """Get a setting value with fallback to default"""
        return self.settings.get(key, default)
        
    def set_setting(self, key, value):
        """Set a setting value and save it"""
        self.settings[key] = value
        self.save_settings()

    def ensure_spinner_visible(self):
        """Helper method to ensure spinner is visible and active"""
        def update_spinner():
            self.spinner.set_property("visible", True)
            self.spinner.set_property("active", True) 
            self.spinner.start()  # Add this explicit call to start the animation
            self.spinner.show_all()
            self.loading_label.set_property("visible", True)
            self.loading_label.show_all()
            
            # Make sure parent containers are visible
            parent = self.spinner.get_parent()
            if parent:
                parent.set_property("visible", True)
                parent.show_all()
            
            # Process events to update UI immediately
            while Gtk.events_pending():
                Gtk.main_iteration()
            return False
            
        # Use GLib.idle_add to ensure UI updates from any thread
        GLib.idle_add(update_spinner)

    def check_internet_connection(self):
        """Check if there is an active internet connection"""
        try:
            # Try to connect to Google's DNS server (most reliable)
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            print("Internet connection check successful: Connected to 8.8.8.8")
            return True
        except (socket.timeout, socket.error, OSError) as e:
            print(f"Connection to 8.8.8.8 failed: {e}")
            try:
                # Try Cloudflare's DNS as a second option
                socket.create_connection(("1.1.1.1", 53), timeout=3)
                print("Internet connection check successful: Connected to 1.1.1.1")
                return True
            except (socket.timeout, socket.error, OSError) as e:
                print(f"Connection to 1.1.1.1 failed: {e}")
                try:
                    # Fall back to HTTP request to Google
                    urllib.request.urlopen("https://www.google.com", timeout=3)
                    print("Internet connection check successful: Connected to google.com")
                    return True
                except Exception as e:
                    print(f"Connection to google.com failed: {e}")
                    try:
                        # Try one more fallback to GitHub (where app data is hosted)
                        urllib.request.urlopen("https://github.com", timeout=3)
                        print("Internet connection check successful: Connected to github.com")
                        return True
                    except Exception as e:
                        print(f"Connection to github.com failed: {e}")
                        print("All connection attempts failed, no internet connectivity detected")
                        return False

    def _ensure_search_box_hidden(self):
        """Make sure the search box stays hidden during UI initialization"""
        if hasattr(self, 'search_box'):
            self.search_box.hide()
        return False  # Don't repeat this callback

    def on_scroll_value_changed(self, adjustment):
        """Handle scroll event to hide search box when scrolling"""
        # Check if scroll position changed significantly (to avoid minor adjustments)
        if abs(adjustment.get_value() - self.last_scroll_position) > 5:
            # Only hide if it's currently visible
            if hasattr(self, 'search_box') and self.search_box.get_visible():
                self.search_box.hide()
                # Update search button icon and tooltip
                if hasattr(self, 'search_button'):
                    self.search_button.set_image(Gtk.Image.new_from_icon_name("system-search-symbolic", Gtk.IconSize.BUTTON))
                    self.search_button.set_tooltip_text("Show Search")
        
        # Update last position
        self.last_scroll_position = adjustment.get_value()

    def _refresh_current_view(self):
        """Refresh only the current view without rebuilding the UI"""
        try:
            # Just refresh the content in the current section
            if hasattr(self, 'current_section'):
                if self.current_section == "explore":
                    # Keep the same category selection and refresh
                    selected_category = self._get_selected_category()
                    self.clear_app_list_box()
                    self.show_apps(selected_category)
                elif self.current_section == "installed":
                    self.clear_app_list_box()
                    self.show_installed_apps()
                elif self.current_section == "updates":
                    self.clear_app_list_box()
                    self.show_update_apps()
            
            # Make sure the UI elements for the current section are properly shown/hidden
            if hasattr(self, 'current_section'):
                # Handle UI elements based on section
                if self.current_section == "explore":
                    if hasattr(self, 'sidebar'):
                        self.sidebar.show()
                    if hasattr(self, 'update_button'):
                        self.update_button.hide()
                elif self.current_section == "installed":
                    if hasattr(self, 'sidebar'):
                        self.sidebar.hide()
                    if hasattr(self, 'update_button'):
                        self.update_button.hide()
                elif self.current_section == "updates":
                    if hasattr(self, 'sidebar'):
                        self.sidebar.hide()
                    if hasattr(self, 'update_button'):
                        self.update_button.show()
        except Exception as e:
            print(f"Error in _refresh_current_view: {e}")
            import traceback
            traceback.print_exc()
        return False

    def check_distro_app_installed_by_path(self, run_cmd, selected_distro):
        """Check if a distro app is installed by checking if its executable exists"""
        if not run_cmd or not selected_distro:
            return False
            
        try:
            print(f"Checking distro app by path: {run_cmd} for distro: {selected_distro}")
            
            # Extract the executable path from run_cmd
            parts = run_cmd.split()
            if not parts:
                return False
                
            executable = parts[0]
            
            # Handle special commands like pdrun
            if executable in ['pdrun', 'AppRun'] and len(parts) > 1:
                executable = parts[1]  # Use the actual executable after pdrun/AppRun
                print(f"Adjusted executable path to: {executable}")
            
            # Check if it's a full path (starts with /)
            if executable.startswith('/'):
                # Check if the file exists in the distro
                check_cmd = f"proot-distro login {selected_distro} --shared-tmp -- /bin/bash -c '[ -f \"{executable}\" ] && [ -x \"{executable}\" ] && echo \"exists\"'"
                print(f"Checking with full path: {check_cmd}")
            else:
                # It's just a command name, check in common bin directories
                check_cmd = f"proot-distro login {selected_distro} --shared-tmp -- /bin/bash -c 'which {executable} > /dev/null 2>&1 && echo \"exists\"'"
                print(f"Checking with which command: {check_cmd}")
            
            result = subprocess.run(['bash', '-c', check_cmd], capture_output=True, text=True)
            exists = result.stdout.strip() == "exists"
            print(f"Check result for {executable}: {'Found' if exists else 'Not found'}")
            
            # If not found, try checking common installation directories based on the executable name
            if not exists and '/' not in executable:
                app_name = executable.lower()
                common_paths = [
                    f"/opt/{app_name}",
                    f"/opt/{app_name.capitalize()}",
                    f"/usr/share/{app_name}",
                    f"/usr/lib/{app_name}",
                    f"/usr/local/bin/{app_name}"
                ]
                
                dir_check_cmd = f"proot-distro login {selected_distro} --shared-tmp -- /bin/bash -c '"
                for path in common_paths:
                    dir_check_cmd += f"[ -d \"{path}\" ] && echo \"exists\" && exit 0; "
                dir_check_cmd += "exit 1'"
                
                print(f"Checking common installation directories: {dir_check_cmd}")
                dir_result = subprocess.run(['bash', '-c', dir_check_cmd], capture_output=True, text=True)
                dir_exists = dir_result.stdout.strip() == "exists"
                if dir_exists:
                    print(f"Found installation directory for {app_name}")
                    exists = True
            
            return exists
            
        except Exception as e:
            print(f"Error checking distro app installation by path: {e}")
            return False

    def is_heavy_operation(self, line):
        """Check if a line contains a heavy operation that should have more weight"""
        # Normalize the line for better pattern matching
        line = line.strip().lower()
        
        # Track the last detected operation to avoid excessive logging
        if not hasattr(self, '_last_heavy_op'):
            self._last_heavy_op = None
            self._heavy_op_count = {}
        
        # List of heavy operations patterns
        heavy_patterns = [
            # Package management operations
            r'(apt|apt-get)\s+(install|upgrade|update|remove|autoremove)',
            r'pacman\s+(-S|-R|-Syu|-Sy)',
            r'dnf\s+(install|upgrade|update|remove)',
            r'yum\s+(install|upgrade|update|remove)',
            r'package_install',
            r'package_remove',
            # Download operations
            r'download_file',
            r'aria2c',
            r'wget',
            r'curl\s+(-O|-o)', 
            # Extraction operations
            r'extract',
            r'tar\s+x',
            r'unzip',
            r'7z\s+x',
            r'unrar\s+x',
            # AppImage installation
            r'install_appimage',
            # System update
            r'update_sys',
            # Direct file operations from the Brave install script
            r'cd\s+/opt/brave-browser',
            r'check_and_delete',
            r'check_and_create_directory',
            r'brave-browser.*\.zip',
            # Specific downloads in the Brave script
            r'.*releases/download.*brave-browser.*\.zip',
            r'githubusercontent\.com'
        ]
        
        # Extract the main operation type for logging purposes
        operation_type = None
        if "download_file" in line:
            operation_type = "download"
        elif "extract" in line:
            operation_type = "extract"
        elif "apt" in line or "pacman" in line or "dnf" in line or "yum" in line:
            operation_type = "package_management"
        elif "check_and" in line:
            operation_type = "file_operation"
        
        # Check if line matches any heavy pattern
        for pattern in heavy_patterns:
            if re.search(pattern, line):
                # Only log the first occurrence of each operation type to reduce spam
                if operation_type:
                    # Only print if different from the last operation or first time seeing
                    if self._last_heavy_op != operation_type:
                        print(f"\n*** HEAVY OPERATION DETECTED: {operation_type} ***\n")
                        self._last_heavy_op = operation_type
                    elif operation_type not in self._heavy_op_count:
                        print(f"\n*** HEAVY OPERATION DETECTED: {operation_type} ***\n")
                        self._heavy_op_count[operation_type] = 1
                    # Count occurrences but limit logging
                    elif self._heavy_op_count[operation_type] < 5:
                        self._heavy_op_count[operation_type] += 1
                        print(f"\n*** HEAVY OPERATION DETECTED: {operation_type} ({self._heavy_op_count[operation_type]}) ***\n")
                    elif self._heavy_op_count[operation_type] == 5:
                        self._heavy_op_count[operation_type] += 1
                        print(f"\n*** HEAVY OPERATION DETECTED: {operation_type} (additional occurrences will not be logged) ***\n")
                return True
                
        return False

    def estimate_line_weight(self, line):
        """Estimate the weight of a script line based on the operation it performs"""
        if self.is_heavy_operation(line):
            # Heavy operations get 3-5x normal weight
            return 4.0
        else:
            # Normal operations get normal weight
            return 1.0

    def update_progress_gradually(self, update_func, start_progress, end_progress, operation_text, duration=3.0):
        """Update progress gradually over time for heavy operations
        
        Args:
            update_func: Function to call to update progress
            start_progress: Starting progress value (0-1)
            end_progress: Ending progress value (0-1)
            operation_text: Text to display in progress bar
            duration: Duration in seconds to spread the progress update
        """
        # Adjust duration based on operation type
        operation_duration = self.get_operation_duration(operation_text)
        duration = max(duration, operation_duration)
        
        # Number of steps to use for the gradual update - more steps for smoother progress
        steps = 50
        step_size = (end_progress - start_progress) / steps
        step_time = duration / steps
        
        # Keep track of the last update time to prevent UI freezing
        last_update_time = [0]
        
        def do_update_step(current_step):
            if current_step >= steps:
                # Final update to ensure we reach the exact end_progress
                GLib.idle_add(update_func, end_progress, operation_text)
                return False
                
            # Calculate current progress
            current_progress = start_progress + (step_size * current_step)
            
            # Update the progress only if enough time has passed (prevents UI freezing)
            current_time = time.time()
            if current_time - last_update_time[0] >= 0.05:  # Update at most 20 times per second
                GLib.idle_add(update_func, current_progress, operation_text)
                last_update_time[0] = current_time
            
            # Schedule next update
            GLib.timeout_add(int(step_time * 1000), do_update_step, current_step + 1)
            return False
            
        # Start the update process immediately with the first step
        GLib.idle_add(update_func, start_progress, operation_text)
        last_update_time[0] = time.time()
        
        # Schedule the second step after a small delay
        GLib.timeout_add(int(step_time * 1000), do_update_step, 1)

    def get_operation_duration(self, operation_text):
        """Determine the appropriate duration for an operation based on its text"""
        operation_lower = operation_text.lower()
        
        # Package management operations (longest)
        if "apt install" in operation_lower or "apt-get install" in operation_lower or "package_install" in operation_lower:
            return 7.0
        elif "pacman -s" in operation_lower or "dnf install" in operation_lower:
            return 7.0
        elif "apt remove" in operation_lower or "apt-get remove" in operation_lower or "package_remove" in operation_lower:
            return 7.0
        elif "pacman -r" in operation_lower or "dnf remove" in operation_lower:
            return 7.0
            
        # Download operations
        elif "download_file" in operation_lower or "aria2c" in operation_lower or "wget" in operation_lower or "curl" in operation_lower:
            return 8.0
            
        # Extraction operations
        elif "extract" in operation_lower or "tar x" in operation_lower or "unzip" in operation_lower:
            return 6.0
        elif "7z x" in operation_lower or "unrar x" in operation_lower:
            return 6.0
            
        # AppImage installation
        elif "install_appimage" in operation_lower:
            return 7.0
            
        # System update
        elif "update_sys" in operation_lower:
            return 9.0
            
        # Base duration for other heavy operations
        return 5.0

class AnsiColorParser:
    """Class to parse ANSI escape sequences and apply formatting to a GTK TextView"""
    
    # ANSI escape sequence regex
    ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[((?:\d+;)*\d+)?([A-Za-z])')
    
    # Basic ANSI color codes
    COLORS = {
        # Foreground colors
        '30': (0.0, 0.0, 0.0),      # Black
        '31': (0.8, 0.0, 0.0),      # Red
        '32': (0.0, 0.8, 0.0),      # Green
        '33': (0.8, 0.8, 0.0),      # Yellow
        '34': (0.0, 0.0, 0.8),      # Blue
        '35': (0.8, 0.0, 0.8),      # Magenta
        '36': (0.0, 0.8, 0.8),      # Cyan
        '37': (0.8, 0.8, 0.8),      # White
        '90': (0.5, 0.5, 0.5),      # Bright Black (Gray)
        '91': (1.0, 0.0, 0.0),      # Bright Red
        '92': (0.0, 1.0, 0.0),      # Bright Green
        '93': (1.0, 1.0, 0.0),      # Bright Yellow
        '94': (0.0, 0.0, 1.0),      # Bright Blue
        '95': (1.0, 0.0, 1.0),      # Bright Magenta
        '96': (0.0, 1.0, 1.0),      # Bright Cyan
        '97': (1.0, 1.0, 1.0),      # Bright White
        # Background colors
        '40': (0.0, 0.0, 0.0),      # Black
        '41': (0.8, 0.0, 0.0),      # Red
        '42': (0.0, 0.8, 0.0),      # Green
        '43': (0.8, 0.8, 0.0),      # Yellow
        '44': (0.0, 0.0, 0.8),      # Blue
        '45': (0.8, 0.0, 0.8),      # Magenta
        '46': (0.0, 0.8, 0.8),      # Cyan
        '47': (0.8, 0.8, 0.8),      # White
        '100': (0.5, 0.5, 0.5),     # Bright Black (Gray)
        '101': (1.0, 0.0, 0.0),     # Bright Red
        '102': (0.0, 1.0, 0.0),     # Bright Green
        '103': (1.0, 1.0, 0.0),     # Bright Yellow
        '104': (0.0, 0.0, 1.0),     # Bright Blue
        '105': (1.0, 0.0, 1.0),     # Bright Magenta
        '106': (0.0, 1.0, 1.0),     # Bright Cyan
        '107': (1.0, 1.0, 1.0),     # Bright White
    }
    
    # Text attributes
    ATTRIBUTES = {
        '0': 'reset',        # Reset all attributes
        '1': 'bold',         # Bold or increased intensity
        '2': 'dim',          # Dim or decreased intensity
        '3': 'italic',       # Italic
        '4': 'underline',    # Underline
        '5': 'blink',        # Blink (not widely supported)
        '7': 'reverse',      # Reverse (swap fg and bg colors)
        '9': 'strikethrough' # Strikethrough
    }
    
    def __init__(self):
        # Initialize tag table for the TextView buffer
        self.tags = {}
    
    def ensure_tag(self, buffer, tag_name, properties):
        """Ensure a tag exists in the buffer with the specified properties"""
        if tag_name not in self.tags:
            tag = buffer.create_tag(tag_name)
            for prop, value in properties.items():
                tag.set_property(prop, value)
            self.tags[tag_name] = tag
        return self.tags[tag_name]
    
    def apply_formatting(self, buffer, text):
        """Parse text with ANSI escape sequences and insert into buffer with appropriate formatting"""
        end_iter = buffer.get_end_iter()
        cursor_pos = 0
        
        # Current formatting state
        fg_color = None
        bg_color = None
        bold = False
        italic = False
        underline = False
        
        # Process the text and find ANSI escape sequences
        for match in self.ANSI_ESCAPE_PATTERN.finditer(text):
            # Insert the text before the escape sequence
            start_pos = match.start()
            if start_pos > cursor_pos:
                plain_text = text[cursor_pos:start_pos]
                # Apply current formatting to plain text
                tags = []
                
                # Create and apply color tags
                if fg_color:
                    fg_tag_name = f"fg_{fg_color[0]}_{fg_color[1]}_{fg_color[2]}"
                    fg_tag = self.ensure_tag(buffer, fg_tag_name, {
                        "foreground-rgba": Gdk.RGBA(*fg_color, 1.0)
                    })
                    tags.append(fg_tag)
                
                if bg_color:
                    bg_tag_name = f"bg_{bg_color[0]}_{bg_color[1]}_{bg_color[2]}"
                    bg_tag = self.ensure_tag(buffer, bg_tag_name, {
                        "background-rgba": Gdk.RGBA(*bg_color, 1.0)
                    })
                    tags.append(bg_tag)
                
                # Apply text attribute tags
                if bold:
                    bold_tag = self.ensure_tag(buffer, "bold", {"weight": Pango.Weight.BOLD})
                    tags.append(bold_tag)
                
                if italic:
                    italic_tag = self.ensure_tag(buffer, "italic", {"style": Pango.Style.ITALIC})
                    tags.append(italic_tag)
                
                if underline:
                    underline_tag = self.ensure_tag(buffer, "underline", 
                                                   {"underline": Pango.Underline.SINGLE})
                    tags.append(underline_tag)
                
                # Insert text with all applicable tags
                start_mark = buffer.create_mark(None, end_iter, True)
                buffer.insert(end_iter, plain_text)
                for tag in tags:
                    start_iter = buffer.get_iter_at_mark(start_mark)
                    buffer.apply_tag(tag, start_iter, end_iter)
                buffer.delete_mark(start_mark)
            
            # Process the escape sequence
            params = match.group(1)
            command = match.group(2)
            
            if command == 'm' and params:  # SGR (Select Graphic Rendition)
                for param in params.split(';'):
                    if not param:
                        continue
                        
                    # Reset all attributes
                    if param == '0':
                        fg_color = None
                        bg_color = None
                        bold = False
                        italic = False
                        underline = False
                    
                    # Process text attributes
                    elif param in self.ATTRIBUTES:
                        attr = self.ATTRIBUTES[param]
                        if attr == 'bold':
                            bold = True
                        elif attr == 'italic':
                            italic = True
                        elif attr == 'underline':
                            underline = True
                    
                    # Process foreground colors
                    elif param in self.COLORS and int(param) < 40:
                        fg_color = self.COLORS[param]
                    
                    # Process background colors
                    elif param in self.COLORS and int(param) >= 40:
                        bg_color = self.COLORS[param]
            
            # Update cursor position
            cursor_pos = match.end()
        
        # Insert any remaining text
        if cursor_pos < len(text):
            remaining_text = text[cursor_pos:]
            # Apply current formatting to remaining text
            tags = []
            
            # Create and apply color tags
            if fg_color:
                fg_tag_name = f"fg_{fg_color[0]}_{fg_color[1]}_{fg_color[2]}"
                fg_tag = self.ensure_tag(buffer, fg_tag_name, {
                    "foreground-rgba": Gdk.RGBA(*fg_color, 1.0)
                })
                tags.append(fg_tag)
            
            if bg_color:
                bg_tag_name = f"bg_{bg_color[0]}_{bg_color[1]}_{bg_color[2]}"
                bg_tag = self.ensure_tag(buffer, bg_tag_name, {
                    "background-rgba": Gdk.RGBA(*bg_color, 1.0)
                })
                tags.append(bg_tag)
            
            # Apply text attribute tags
            if bold:
                bold_tag = self.ensure_tag(buffer, "bold", {"weight": Pango.Weight.BOLD})
                tags.append(bold_tag)
            
            if italic:
                italic_tag = self.ensure_tag(buffer, "italic", {"style": Pango.Style.ITALIC})
                tags.append(italic_tag)
            
            if underline:
                underline_tag = self.ensure_tag(buffer, "underline", 
                                               {"underline": Pango.Underline.SINGLE})
                tags.append(underline_tag)
            
            # Insert text with all applicable tags
            start_mark = buffer.create_mark(None, end_iter, True)
            buffer.insert(end_iter, remaining_text)
            for tag in tags:
                start_iter = buffer.get_iter_at_mark(start_mark)
                buffer.apply_tag(tag, start_iter, end_iter)
            buffer.delete_mark(start_mark)
    
    def strip_ansi(self, text):
        """Remove ANSI escape sequences from text"""
        return self.ANSI_ESCAPE_PATTERN.sub('', text)

class TerminalEmulator:
    """Emulates a terminal in a GTK TextView"""
    
    def __init__(self, text_view):
        self.text_view = text_view
        self.buffer = text_view.get_buffer()
        self.ansi_parser = AnsiColorParser()
        
        # Ensure monospace font for terminal-like appearance
        self.text_view.set_monospace(True)
        
        # Set initial terminal colors
        self.text_view.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 1))
        self.text_view.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(1, 1, 1, 1))
        
        # Add terminal view style class
        self.text_view.get_style_context().add_class("terminal-view")
    
    def append_text(self, text, with_ansi=True):
        """Append text to the terminal view, processing ANSI escape sequences if with_ansi is True"""
        if not text:
            return
            
        # Check if we need to add a newline before the new text
        if self.buffer.get_char_count() > 0:
            # Get the last character in the buffer
            end_iter = self.buffer.get_end_iter()
            start_iter = end_iter.copy()
            if start_iter.backward_char():  # This returns False if we can't move back (empty buffer)
                last_char = self.buffer.get_text(start_iter, end_iter, False)
                
                # If the last character isn't a newline and the new text doesn't start with one,
                # add a newline before the new text
                if last_char != '\n' and not text.startswith('\n'):
                    # Insert a newline first
                    self.buffer.insert(end_iter, '\n')
            
        # Process text with ANSI escape sequences
        if with_ansi:
            self.ansi_parser.apply_formatting(self.buffer, text)
        else:
            # Just append the text without processing
            end_iter = self.buffer.get_end_iter()
            self.buffer.insert(end_iter, text)
        
        # Scroll to the end
        mark = self.buffer.create_mark(None, self.buffer.get_end_iter(), False)
        self.text_view.scroll_mark_onscreen(mark)
        self.buffer.delete_mark(mark)
    
    def clear(self):
        """Clear the terminal view"""
        self.buffer.delete(self.buffer.get_start_iter(), self.buffer.get_end_iter())
    
    def get_text(self):
        """Get the terminal contents"""
        start_iter, end_iter = self.buffer.get_bounds()
        return self.buffer.get_text(start_iter, end_iter, False)

def main():
    app = AppStoreApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)

