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
UPDATES_TRACKING_FILE = os.path.expanduser("~/.termux_appstore/updates.json")

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
        Gtk.Application.__init__(
            self,
            application_id="org.sabamdarif.termux.appstore",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self.window = None
        # Connect the activate signal
        self.connect('activate', self.on_activate)

    def do_startup(self):
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
        """Handler for the application's activate signal"""
        if not self.window:
            self.window = AppStoreWindow(self)
        self.window.present()

class AppStoreWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        try:
            Gtk.ApplicationWindow.__init__(
                self,
                application=app,
                title="Termux AppStore"
            )
            
            # Initialize thread pool and queues
            self.thread_pool = ThreadPoolExecutor(max_workers=4)
            self.ui_update_queue = queue.Queue()
            
            # Start UI update thread
            self.ui_update_thread = threading.Thread(target=self.process_ui_updates, daemon=True)
            self.ui_update_thread.start()
            
            # Add a timer for periodic UI updates
            GLib.timeout_add(100, self.process_pending_ui_updates)
            
            # Set window properties
            self.set_wmclass("termux-appstore", "Termux AppStore")
            self.set_role("termux-appstore")
            self.set_default_size(1000, 600)
            self.set_position(Gtk.WindowPosition.CENTER)
            
            # Initialize installation flags
            self.installation_cancelled = False
            self.uninstallation_cancelled = False

            # Get system architecture
            self.system_arch = platform.machine().lower()
            print(f"System architecture: {self.system_arch}")
            
            # Define architecture compatibility groups
            self.arch_compatibility = {
                'arm64': ['arm64', 'aarch64'],
                'aarch64': ['arm64', 'aarch64'],
                'arm': ['arm', 'armhf', 'armv7', 'armv7l', 'armv7a', 'armv8l'],
                'armv7l': ['arm', 'armhf', 'armv7', 'armv7l', 'armv7a', 'armv8l'],
                'armhf': ['arm', 'armhf', 'armv7', 'armv7l', 'armv7a', 'armv8l'],
                'armv8l': ['arm', 'armhf', 'armv7', 'armv7l', 'armv7a', 'armv8l']
            }

            # Add keyboard accelerators
            accel = Gtk.AccelGroup()
            self.add_accel_group(accel)
            
            # Add Ctrl+Q shortcut
            key, mod = Gtk.accelerator_parse("<Control>Q")
            accel.connect(key, mod, Gtk.AccelFlags.VISIBLE, self.on_quit_accelerator)

            # Initialize stop flag for background tasks
            self.stop_background_tasks = False

            # Initialize task queue and current task
            self.task_queue = queue.Queue()
            self.current_task = None

            # Start task processor
            self.start_task_processor()

            # Connect the delete-event to handle window closing
            self.connect("delete-event", self.on_delete_event)

            # Initialize paths and create directories
            self.setup_directories()

            # Initialize installed apps tracking
            self.installed_apps_file = Path(os.path.expanduser("~/.termux_appstore/installed_apps.json"))
            self.installed_apps_file.parent.mkdir(parents=True, exist_ok=True)
            self.load_installed_apps()

            # Initialize categories and apps data
            self.categories = []
            self.apps_data = []

            # Load CSS
            css_provider = Gtk.CssProvider()
            css_file = Path("/data/data/com.termux/files/usr/opt/appstore/style/style.css")
            css_provider.load_from_path(str(css_file))
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            # Create main container with overlay
            self.overlay = Gtk.Overlay()
            self.add(self.overlay)

            # Create main content box
            self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.overlay.add(self.main_box)

            # Create spinner for initial load
            self.spinner = Gtk.Spinner()
            self.spinner.set_size_request(64, 64)

            # Create a label for the loading message
            self.loading_label = Gtk.Label(label="This process will take some time. Please wait...")
            self.loading_label.set_halign(Gtk.Align.CENTER)
            self.loading_label.hide()

            spinner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            spinner_box.pack_start(self.spinner, True, True, 0)
            spinner_box.pack_start(self.loading_label, True, True, 0)
            spinner_box.set_valign(Gtk.Align.CENTER)
            spinner_box.set_halign(Gtk.Align.CENTER)
            self.overlay.add_overlay(spinner_box)

            # Create header bar
            header = Gtk.HeaderBar()
            header.set_show_close_button(True)
            header.props.title = "Termux AppStore"
            
            # Add refresh button to header bar
            # self.refresh_button = Gtk.Button()
            # refresh_icon = Gio.ThemedIcon(name="view-refresh-symbolic")
            # refresh_image = Gtk.Image.new_from_gicon(refresh_icon, Gtk.IconSize.BUTTON)
            # self.refresh_button.add(refresh_image)
            # self.refresh_button.connect("clicked", lambda x: self.start_refresh(is_manual=True))
            # header.pack_start(self.refresh_button)

            # Handle refresh button click
            # def on_refresh_clicked(self, button):
            #     """Handle refresh button click"""
            #     # Start the refresh process
            #     self.start_refresh()

            # Remove references to refresh_button
            # self.refresh_button.set_sensitive(False)
            # self.refresh_button.set_sensitive(True)

            self.set_titlebar(header)

            # Create section buttons box
            section_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            section_box.get_style_context().add_class('linked')  # This makes buttons appear connected
            
            # Explore button
            self.explore_button = Gtk.Button(label="Explore")
            self.explore_button.connect("clicked", self.on_section_clicked, "explore")
            self.explore_button.get_style_context().add_class('section-button')
            self.explore_button.get_style_context().add_class('selected')
            section_box.pack_start(self.explore_button, False, False, 0)
            
            # Installed button
            self.installed_button = Gtk.Button(label="Installed")
            self.installed_button.connect("clicked", self.on_section_clicked, "installed")
            self.installed_button.get_style_context().add_class('section-button')
            section_box.pack_start(self.installed_button, False, False, 0)
            
            # Updates button
            self.updates_button = Gtk.Button(label="Updates")
            self.updates_button.connect("clicked", self.on_section_clicked, "updates")
            self.updates_button.get_style_context().add_class('section-button')
            section_box.pack_start(self.updates_button, False, False, 0)
            
            # Add section buttons to center of header
            header.set_custom_title(section_box)

            # Create content box for app list
            self.content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            self.main_box.pack_start(self.content_box, True, True, 0)

            # Show all widgets
            self.show_all()

            # Start the initial data load
            self.check_for_updates()

            # Initialize updates tracking
            self.updates_tracking_file = os.path.expanduser("~/.termux_appstore/updates.json")
            os.makedirs(os.path.dirname(self.updates_tracking_file), exist_ok=True)
            self.pending_updates = self.load_pending_updates()

        except Exception as e:
            print(f"Error initializing AppStoreWindow: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    def setup_directories(self):
        """Create necessary directories for the app store"""
        os.makedirs(APPSTORE_DIR, exist_ok=True)
        os.makedirs(APPSTORE_LOGO_DIR, exist_ok=True)

    def check_for_updates(self):
        print('Checking for updates...')
        try:
            # Check when was the last version update
            last_version_check_file = os.path.expanduser("~/.termux_appstore/last_version_check")
            current_time = datetime.now()

            if os.path.exists(last_version_check_file):
                with open(last_version_check_file, 'r') as f:
                    last_check = datetime.fromtimestamp(float(f.read().strip()))
                    if current_time - last_check < timedelta(days=1):
                        print("Version check performed within last 24 hours, skipping...")
                        # Load app metadata and setup UI first
                        thread = threading.Thread(target=self.load_app_metadata_and_setup_ui)
                        thread.daemon = True
                        thread.start()
                        return

            # If we reach here, we need to update versions
            print("Performing daily version check...")
            self.start_refresh(is_manual=False)
            
            # Update last check time
            with open(last_version_check_file, 'w') as f:
                f.write(str(current_time.timestamp()))

        except Exception as e:
            print(f"Error checking updates: {e}")
            self.start_refresh(is_manual=False)

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
            distro_enabled = False
            selected_distro = None
            
            if os.path.exists(termux_desktop_config):
                try:
                    with open(termux_desktop_config, 'r') as f:
                        for line in f:
                            if line.startswith('distro_add_answer='):
                                distro_enabled = line.strip().split('=')[1].lower() == 'y'
                            elif line.startswith('selected_distro='):
                                selected_distro = line.strip().split('=')[1].lower()
                except Exception as e:
                    print(f"Error reading Termux Desktop config: {e}")
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
            GLib.idle_add(self.show_apps)

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
        """Hide both spinner and loading label"""
        self.spinner.stop()
        self.spinner.hide()
        self.loading_label.hide()
        return False

    def start_refresh(self, is_manual=True):
        """Start the refresh process in a background thread"""
        print("\nStarting refresh process...")
        
        # Store is_manual flag as instance variable
        self.is_manual_refresh = is_manual
        
        # Clear existing content
        for child in self.content_box.get_children():
            child.destroy()

        # Show and start spinner
        self.spinner.show()
        self.spinner.start()
        self.loading_label.show()
        # self.refresh_button.set_sensitive(False)

        # Start background thread for downloading
        thread = threading.Thread(target=self.refresh_data_background)
        thread.daemon = True
        thread.start()

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
            command = f"aria2c -x 16 -s 16 '{logos_url}' -d '{TERMUX_TMP}' -o 'logos.zip'"
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Failed to download logos: {result.stderr}")
                return False
            
            # Create logo directory
            os.makedirs(APPSTORE_LOGO_DIR, exist_ok=True)
            
            # Extract logos
            print("Extracting logos...")
            command = f"unzip -o '{logos_zip}' -d '{APPSTORE_LOGO_DIR}'"
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            # Clean up zip file
            if os.path.exists(logos_zip):
                os.remove(logos_zip)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"Error handling logos: {e}")
            return False

    def refresh_data_background(self):
        try:
            print("\nStarting refresh process...")
            
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
            distro_enabled = False
            selected_distro = None
            
            if os.path.exists(termux_desktop_config):
                try:
                    with open(termux_desktop_config, 'r') as f:
                        for line in f:
                            if line.startswith('distro_add_answer='):
                                distro_enabled = line.strip().split('=')[1].lower() == 'y'
                            elif line.startswith('selected_distro='):
                                selected_distro = line.strip().split('=')[1].lower()
                except Exception as e:
                    print(f"Error reading Termux Desktop config: {e}")
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
                            if app['app_type'] == 'distro':
                                supported_distro = app.get('supported_distro')
                                if supported_distro and supported_distro != 'all':
                                    # Split supported_distro into a list if it contains commas
                                    supported_distros = [d.strip().lower() for d in supported_distro.split(',')]
                                    if selected_distro not in supported_distros:
                                        print(f"Skipping {app['app_name']}: not compatible with {selected_distro}")
                                        continue

                                # Try distro-specific package name first
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

    def refresh_complete(self):
        """Called when refresh is complete"""
        print('Refresh complete!')
        
        # Load app metadata first
        self.load_app_metadata()
        
        # Clear current content
        for child in self.content_box.get_children():
            child.destroy()
        
        # Hide loading indicators
        self.spinner.stop()
        self.spinner.hide()
        self.loading_label.hide()
        # self.refresh_button.set_sensitive(True)

        # Setup UI with the new data
        self.setup_app_list_ui()
        
        # Refresh the display to show updated buttons
        self.show_apps()
        
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
        GLib.idle_add(self.show_apps)

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
            distro_enabled = False
            selected_distro = None
            
            if os.path.exists(termux_desktop_config):
                try:
                    with open(termux_desktop_config, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('#') or not line:
                                continue
                            if line.startswith('distro_add_answer='):
                                value = line.split('=')[1].strip().strip('"').lower()  # Remove quotes
                                self.distro_add_answer = value
                                print(f"Found distro_add_answer: {value} -> enabled: {distro_enabled}")
                            elif line.startswith('selected_distro='):
                                selected_distro = line.split('=')[1].strip().strip('"').lower()  # Remove quotes
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
        all_button.set_size_request(-1, 40)
        all_button.get_style_context().add_class("category-button")
        all_button.get_style_context().add_class("selected")
        self.sidebar.pack_start(all_button, False, True, 0)

        # Category buttons
        self.category_buttons = [all_button]
        for category in sorted(self.categories):
            button = Gtk.Button(label=category)
            button.connect("clicked", self.on_category_clicked)
            button.set_size_request(-1, 40)
            button.get_style_context().add_class("category-button")
            self.sidebar.pack_start(button, False, True, 0)
            self.category_buttons.append(button)

        # Right panel container
        self.right_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.content_box.pack_start(self.right_panel, True, True, 0)

        # Add search entry at the top of app list
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        search_box.set_margin_start(10)
        search_box.set_margin_end(10)
        search_box.set_margin_top(10)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search apps...")
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.search_entry.set_size_request(-1, 40)
        search_box.pack_start(self.search_entry, True, True, 0)
        self.right_panel.pack_start(search_box, False, True, 0)

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
        # Update selected state of category buttons
        for btn in self.category_buttons:
            btn.get_style_context().remove_class('selected')
        button.get_style_context().add_class('selected')

        category = button.get_label()
        # Clear search when changing categories
        self.search_entry.set_text("")
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
            # Create progress dialog with fixed width but expandable height
            progress_dialog = Gtk.Dialog(
                title="Installing...",
                parent=self,
                modal=True
            )
            progress_dialog.set_default_size(350, 150)  # Set initial size
            progress_dialog.set_resizable(True)  # Allow resizing
            
            # Add minimize button to titlebar
            header = Gtk.HeaderBar()
            header.set_show_close_button(False)
            minimize_button = Gtk.Button()
            minimize_button.set_relief(Gtk.ReliefStyle.NONE)
            minimize_icon = Gtk.Image.new_from_icon_name("window-minimize", Gtk.IconSize.MENU)
            minimize_button.add(minimize_icon)
            minimize_button.connect("clicked", lambda x: progress_dialog.iconify())
            header.pack_end(minimize_button)
            progress_dialog.set_titlebar(header)
            
            # Add cancel button and connect to response signal
            cancel_button = progress_dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
            
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            vbox.set_margin_start(10)
            vbox.set_margin_end(10)
            vbox.set_margin_top(10)
            vbox.set_margin_bottom(10)
            
            # Status label with better text handling
            status_label = Gtk.Label()
            status_label.set_line_wrap(True)
            status_label.set_line_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            status_label.set_justify(Gtk.Justification.LEFT)
            status_label.set_halign(Gtk.Align.START)
            status_label.set_text("Starting installation...")
            
            # Create a scrolled window for status label that expands
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scroll.set_size_request(-1, 80)  # Minimum height
            scroll.add(status_label)
            vbox.pack_start(scroll, True, True, 0)  # Allow vertical expansion
            
            # Progress bar that expands horizontally
            progress_bar = Gtk.ProgressBar()
            progress_bar.set_show_text(True)
            progress_bar.set_size_request(300, -1)
            vbox.pack_start(progress_bar, False, True, 0)
            
            progress_dialog.get_content_area().add(vbox)
            progress_dialog.show_all()

            # Track current process and script path
            current_process = {'process': None}
            script_path = [None]  # Use list to allow modification in nested functions

            def on_cancel_clicked(dialog, response_id):
                if response_id == Gtk.ResponseType.CANCEL:
                    # Set cancellation flag
                    self.installation_cancelled = True
                    
                    # Terminate current process if it exists
                    if current_process['process']:
                        try:
                            current_process['process'].terminate()
                            current_process['process'].wait()
                        except:
                            pass  # Process might have already ended
                    
                    # Clean up script if it exists
                    if script_path[0] and os.path.exists(script_path[0]):
                        try:
                            os.remove(script_path[0])
                        except:
                            pass
                    
                    dialog.destroy()

            # Connect the response signal
            progress_dialog.connect('response', on_cancel_clicked)

            def update_progress(fraction, status_text):
                if not status_text:
                    return False
                
                # Parse aria2c download progress format
                if '[#' in status_text and ']' in status_text:
                    # Extract progress details from aria2c output
                    progress_part = status_text[status_text.find('['):status_text.find(']')+1]
                    file_part = status_text[status_text.find(']')+1:].strip()
                    
                    # Format the status text to show both progress and file
                    status_label.set_text(f"{progress_part}\n{file_part}")
                elif isinstance(status_text, str) and status_text.strip() and not all(c in '-' for c in status_text.strip()):
                    status_label.set_text(status_text)
                
                progress_bar.set_fraction(fraction)
                progress_bar.set_text(f"{int(fraction * 100)}%")
                return False

            def install_thread():
                try:
                    # Download script (20%)
                    GLib.idle_add(update_progress, 0.2, "Downloading install script...")
                    script_path[0] = self.download_script(app['install_url'])
                    if not script_path[0] or self.installation_cancelled:
                        if script_path[0] and os.path.exists(script_path[0]):
                            os.remove(script_path[0])
                        GLib.idle_add(progress_dialog.destroy)
                        return

                    # Make script executable (30%)
                    GLib.idle_add(update_progress, 0.3, "Preparing installation...")
                    os.chmod(script_path[0], os.stat(script_path[0]).st_mode | stat.S_IEXEC)

                    # Execute script with better progress tracking
                    GLib.idle_add(update_progress, 0.4, "Starting installation...")
                    process = subprocess.Popen(
                        ['bash', script_path[0]],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1
                    )
                    
                    # Store process reference for cancellation
                    current_process['process'] = process

                    for line in process.stdout:
                        if self.installation_cancelled:
                            process.terminate()
                            process.wait()
                            GLib.idle_add(progress_dialog.destroy)
                            return

                        line = line.strip()
                        progress = 0.4

                        # Update progress based on specific actions
                        if "download" in line.lower():
                            progress = 0.5
                        elif "extracting" in line.lower() or "tar" in line.lower():
                            progress = 0.7
                        elif "installing" in line.lower():
                            progress = 0.8
                        elif "creating desktop entry" in line.lower():
                            progress = 0.9

                        if line:  # Only update if line is not empty
                            GLib.idle_add(update_progress, progress, line)

                    process.wait()
                    if process.returncode == 0 and not self.installation_cancelled:
                        GLib.idle_add(update_progress, 0.95, "Finalizing installation...")
                        GLib.idle_add(lambda: self.update_installation_status(app['folder_name'], True))
                        
                        # Remove from pending updates if this was an update
                        if app['folder_name'] in self.pending_updates:
                            del self.pending_updates[app['folder_name']]
                            self.save_pending_updates()
                        
                        time.sleep(0.5)
                        GLib.idle_add(update_progress, 1.0, "Installation complete!")
                        time.sleep(1)
                        GLib.idle_add(progress_dialog.destroy)
                        GLib.idle_add(self.show_apps)  # Refresh the UI
                    else:
                        GLib.idle_add(update_progress, 1.0, "Installation failed!")
                        time.sleep(2)
                        GLib.idle_add(progress_dialog.destroy)

                except Exception as e:
                    print(f"Installation error: {str(e)}")
                    GLib.idle_add(update_progress, 1.0, f"Error: {str(e)}")
                    time.sleep(2)
                    GLib.idle_add(progress_dialog.destroy)
                
                finally:
                    current_process['process'] = None
                    if script_path[0] and os.path.exists(script_path[0]):
                        try:
                            os.remove(script_path[0])
                            print(f"Cleaned up script: {script_path[0]}")
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
            progress_dialog = Gtk.Dialog(
                title="Uninstalling...",
                parent=self,
                flags=0
            )
            progress_dialog.set_default_size(400, -1)
            progress_dialog.set_resizable(False)
            progress_dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
            
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            vbox.set_margin_start(20)
            vbox.set_margin_end(20)
            vbox.set_margin_top(20)
            vbox.set_margin_bottom(20)
            
            status_label = Gtk.Label()
            status_label.set_line_wrap(True)
            status_label.set_line_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            status_label.set_max_width_chars(50)
            status_label.set_width_chars(50)
            status_label.set_justify(Gtk.Justification.LEFT)
            status_label.set_halign(Gtk.Align.START)
            status_label.set_text("Starting uninstallation...")
            vbox.pack_start(status_label, True, True, 0)
            
            progress_bar = Gtk.ProgressBar()
            progress_bar.set_show_text(True)
            progress_bar.set_size_request(360, -1)
            vbox.pack_start(progress_bar, True, True, 0)
            
            progress_dialog.get_content_area().add(vbox)
            progress_dialog.show_all()

            def update_progress(fraction, status_text):
                if status_text and not status_text.strip('-'):
                    status_label.set_text(status_text)
                progress_bar.set_fraction(fraction)
                progress_bar.set_text(f"{int(fraction * 100)}%")
                return False

            def uninstall_thread():
                script_path = None
                try:
                    # Download script
                    GLib.idle_add(update_progress, 0.2, "Downloading uninstall script...")
                    script_path = self.download_script(app['uninstall_url'])
                    if not script_path or self.uninstallation_cancelled:
                        if script_path and os.path.exists(script_path):
                            os.remove(script_path)
                        GLib.idle_add(progress_dialog.destroy)
                        return

                    os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)

                    process = subprocess.Popen(
                        script_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1
                    )

                    for line in process.stdout:
                        if self.uninstallation_cancelled:
                            process.terminate()
                            process.wait()
                            GLib.idle_add(progress_dialog.destroy)
                            return
                        
                        GLib.idle_add(update_progress, 0.5, line.strip())

                    process.wait()
                    if process.returncode == 0 and not self.uninstallation_cancelled:
                        GLib.idle_add(update_progress, 0.95, "Finalizing uninstallation...")
                        self.installed_apps.remove(app['folder_name'])
                        self.save_installed_apps()
                        GLib.idle_add(self.show_apps)
                        GLib.idle_add(update_progress, 1.0, "Uninstallation complete!")
                        time.sleep(1)
                        GLib.idle_add(progress_dialog.destroy)
                    else:
                        GLib.idle_add(update_progress, 1.0, "Uninstallation failed!")
                        time.sleep(2)
                        GLib.idle_add(progress_dialog.destroy)

                except Exception as e:
                    print(f"Uninstallation error: {str(e)}")
                    GLib.idle_add(update_progress, 1.0, f"Error: {str(e)}")
                    time.sleep(2)
                    GLib.idle_add(progress_dialog.destroy)
                
                finally:
                    # Clean up downloaded script
                    if script_path and os.path.exists(script_path):
                        try:
                            os.remove(script_path)
                            print(f"Cleaned up script: {script_path}")
                        except Exception as e:
                            print(f"Error cleaning up script: {e}")

            thread = threading.Thread(target=uninstall_thread)
            thread.daemon = True
            thread.start()

    def show_apps(self, category=None):
        """Display apps based on category"""
        try:
            # Clear current list safely
            GLib.idle_add(self.clear_app_list_box)

            # Filter apps based on category and search query
            filtered_apps = self.apps_data
            if category and category != "All Apps":
                filtered_apps = [app for app in filtered_apps if category in app['categories']]

            # Apply search filter if search entry has text
            search_text = self.search_entry.get_text().lower()
            if search_text:
                filtered_apps = [
                    app for app in filtered_apps
                    if search_text in app['app_name'].lower()
                    or search_text in app['description'].lower()
                    or any(search_text in cat.lower() for cat in app['categories'])
                ]

            # Add filtered apps to the list using idle_add
            for app in filtered_apps:
                GLib.idle_add(lambda a=app: self.add_app_card(a))

            GLib.idle_add(self.app_list_box.show_all)
        except Exception as e:
            print(f"Error in show_apps: {e}")
            import traceback
            traceback.print_exc()

    def clear_app_list_box(self):
        """Safely clear the app list box"""
        try:
            for child in self.app_list_box.get_children():
                self.app_list_box.remove(child)
                child.destroy()
            return False
        except Exception as e:
            print(f"Error clearing app list box: {e}")
            return False

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

            # App logo with error handling
            logo_path = os.path.join(APPSTORE_LOGO_DIR, app['folder_name'], 'logo.png')
            if os.path.exists(logo_path):
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
        # Get the currently selected section
        selected_section = None
        if self.explore_button.get_style_context().has_class('selected'):
            selected_section = "explore"
        elif self.installed_button.get_style_context().has_class('selected'):
            selected_section = "installed"
        elif self.updates_button.get_style_context().has_class('selected'):
            selected_section = "updates"
        
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
            self.show_apps(selected_category)
        elif selected_section == "installed":
            self.show_installed_apps()
        elif selected_section == "updates":
            self.show_update_apps()

    def on_delete_event(self, widget, event):
        """Handle window closing"""
        self.stop_background_tasks = True
        sys.exit(0)
        return False

    def refresh_error(self, error_message):
        """Handle refresh error"""
        print(f"Refresh error: {error_message}")
        # Implement additional error handling logic here if needed

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

            subprocess.Popen(['bash', '-c', run_cmd])
        except Exception as e:
            self.show_error_dialog(f"Error opening app: {e}")

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
        self.stop_task_processor()
        sys.exit(0)

    def on_quit_accelerator(self, accel_group, acceleratable, keyval, modifier):
        """Handle Ctrl+Q accelerator"""
        self.on_delete_event(None, None)
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
            os.makedirs(os.path.dirname(self.updates_tracking_file), exist_ok=True)
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
                # Create progress dialog with fixed width but expandable height
                progress_dialog = Gtk.Dialog(
                    title="Updating...",
                    parent=self,
                    modal=True
                )
                progress_dialog.set_default_size(350, 150)  # Set initial size
                progress_dialog.set_resizable(True)  # Allow resizing
                
                # Add minimize button to titlebar
                header = Gtk.HeaderBar()
                header.set_show_close_button(False)
                minimize_button = Gtk.Button()
                minimize_button.set_relief(Gtk.ReliefStyle.NONE)
                minimize_icon = Gtk.Image.new_from_icon_name("window-minimize", Gtk.IconSize.MENU)
                minimize_button.add(minimize_icon)
                minimize_button.connect("clicked", lambda x: progress_dialog.iconify())
                header.pack_end(minimize_button)
                progress_dialog.set_titlebar(header)
                
                # Add cancel button and connect to response signal
                cancel_button = progress_dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
                
                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
                vbox.set_margin_start(10)
                vbox.set_margin_end(10)
                vbox.set_margin_top(10)
                vbox.set_margin_bottom(10)
                
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
                scroll.set_size_request(-1, 80)  # Minimum height
                scroll.add(status_label)
                vbox.pack_start(scroll, True, True, 0)  # Allow vertical expansion
                
                # Progress bar that expands horizontally
                progress_bar = Gtk.ProgressBar()
                progress_bar.set_show_text(True)
                progress_bar.set_size_request(300, -1)
                vbox.pack_start(progress_bar, False, True, 0)
                
                progress_dialog.get_content_area().add(vbox)
                progress_dialog.show_all()

                # Track current process and script path
                current_process = {'process': None}
                script_path = [None]  # Use list to allow modification in nested functions

                def on_cancel_clicked(dialog, response_id):
                    if response_id == Gtk.ResponseType.CANCEL:
                        # Set cancellation flag
                        self.installation_cancelled = True
                        
                        # Terminate current process if it exists
                        if current_process['process']:
                            try:
                                current_process['process'].terminate()
                                current_process['process'].wait()
                            except:
                                pass  # Process might have already ended
                        
                        # Clean up script if it exists
                        if script_path[0] and os.path.exists(script_path[0]):
                            try:
                                os.remove(script_path[0])
                            except:
                                pass
                        
                        dialog.destroy()

                # Connect the response signal
                progress_dialog.connect('response', on_cancel_clicked)

                def update_progress(fraction, status_text):
                    if not status_text:
                        return False
                    
                    # Parse aria2c download progress format
                    if '[#' in status_text and ']' in status_text:
                        # Extract progress details from aria2c output
                        progress_part = status_text[status_text.find('['):status_text.find(']')+1]
                        file_part = status_text[status_text.find(']')+1:].strip()
                        
                        # Format the status text to show both progress and file
                        status_label.set_text(f"{progress_part}\n{file_part}")
                    elif isinstance(status_text, str) and status_text.strip():
                        status_label.set_text(status_text)
                    
                    progress_bar.set_fraction(fraction)
                    progress_bar.set_text(f"{int(fraction * 100)}%")
                    return False

                def install_thread():
                    try:
                        # Download script (20%)
                        GLib.idle_add(update_progress, 0.2, "Downloading install script...")
                        script_path[0] = self.download_script(app['install_url'])
                        if not script_path[0] or self.installation_cancelled:
                            if script_path[0] and os.path.exists(script_path[0]):
                                os.remove(script_path[0])
                            GLib.idle_add(progress_dialog.destroy)
                            return

                        # Make script executable (30%)
                        GLib.idle_add(update_progress, 0.3, "Preparing update...")
                        os.chmod(script_path[0], os.stat(script_path[0]).st_mode | stat.S_IEXEC)

                        # Execute script with better progress tracking
                        GLib.idle_add(update_progress, 0.4, "Starting update...")
                        process = subprocess.Popen(
                            ['bash', script_path[0]],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            universal_newlines=True,
                            bufsize=1
                        )
                        
                        # Store process reference for cancellation
                        current_process['process'] = process

                        for line in process.stdout:
                            if self.installation_cancelled:
                                process.terminate()
                                process.wait()
                                GLib.idle_add(progress_dialog.destroy)
                                return

                            line = line.strip()
                            progress = 0.4

                            # Update progress based on specific actions
                            if "download" in line.lower():
                                progress = 0.5
                            elif "extracting" in line.lower() or "tar" in line.lower():
                                progress = 0.7
                            elif "installing" in line.lower():
                                progress = 0.8
                            elif "creating desktop entry" in line.lower():
                                progress = 0.9

                            if line:  # Only update if line is not empty
                                GLib.idle_add(update_progress, progress, line)

                        process.wait()
                        if process.returncode == 0 and not self.installation_cancelled:
                            GLib.idle_add(update_progress, 0.95, "Finalizing update...")
                            
                            # Remove from pending updates
                            if app['folder_name'] in self.pending_updates:
                                del self.pending_updates[app['folder_name']]
                                self.save_pending_updates()
                                print(f"Removed {app['app_name']} from pending updates")
                            
                            # Update the app's version in apps.json
                            try:
                                with open(APPSTORE_JSON, 'r') as f:
                                    apps_data = json.load(f)
                                for app_data in apps_data:
                                    if app_data['folder_name'] == app['folder_name']:
                                        app_data['version'] = self.pending_updates.get(app['folder_name'], app_data['version'])
                                with open(APPSTORE_JSON, 'w') as f:
                                    json.dump(apps_data, f, indent=2)
                            except Exception as e:
                                print(f"Error updating version in apps.json: {e}")
                            
                            time.sleep(0.5)
                            GLib.idle_add(update_progress, 1.0, "Update complete!")
                            time.sleep(1)
                            GLib.idle_add(progress_dialog.destroy)
                            
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
                            GLib.idle_add(progress_dialog.destroy)

                    except Exception as e:
                        print(f"Update error: {str(e)}")
                        GLib.idle_add(update_progress, 1.0, f"Error: {str(e)}")
                        time.sleep(2)
                        GLib.idle_add(progress_dialog.destroy)
                    
                    finally:
                        current_process['process'] = None
                        if script_path[0] and os.path.exists(script_path[0]):
                            try:
                                os.remove(script_path[0])
                                print(f"Cleaned up script: {script_path[0]}")
                            except Exception as e:
                                print(f"Error cleaning up script: {e}")

                thread = threading.Thread(target=install_thread)
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
            GLib.idle_add(update)

        def update_system_thread():
            try:
                # Step 1: Update Repository (0-40%)
                print("\n=== Checking Package Manager ===")
                update_progress_safe(0)
                
                cmd = "source /data/data/com.termux/files/usr/bin/termux-setup-package-manager && echo $TERMUX_APP_PACKAGE_MANAGER"
                result = subprocess.run(['bash', '-c', cmd], capture_output=True, text=True)
                pkg_manager = result.stdout.strip()
                print(f"Detected package manager: {pkg_manager}")

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
                distro_enabled = False
                selected_distro = None
                
                if os.path.exists(termux_desktop_config):
                    try:
                        with open(termux_desktop_config, 'r') as f:
                            for line in f:
                                if line.startswith('distro_add_answer='):
                                    distro_enabled = line.strip().split('=')[1].lower() == 'y'
                                elif line.startswith('selected_distro='):
                                    selected_distro = line.strip().split('=')[1].lower()
                    except Exception as e:
                        print(f"Error reading Termux Desktop config: {e}")

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
                
                # Reset button and refresh display
                GLib.idle_add(self.update_complete)
                GLib.idle_add(self.show_update_apps)
                
            except Exception as e:
                print(f"\n=== Update Check Failed ===")
                print(f"Error: {str(e)}")
                print(f"Stack trace:")
                import traceback
                traceback.print_exc()
                GLib.idle_add(lambda: self.show_error_dialog(f"Update check failed: {str(e)}"))
                GLib.idle_add(self.update_complete)

        # Submit the update task to the thread pool
        self.thread_pool.submit(update_system_thread)

    def update_progress(self, progress):
        """Update the progress bar effect on button"""
        css = f"""
            .updating {{
                background-image: linear-gradient(to right, @theme_selected_bg_color 0%, 
                    @theme_selected_bg_color {progress}%, transparent {progress}%);
            }}
        """
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode())
        self.update_button.get_style_context().add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        return True

    def update_complete(self):
        """Reset update button state after update completes"""
        self.update_button.set_sensitive(True)
        self.update_button.set_label("Check for Updates")
        self.update_button.get_style_context().remove_class('updating')
        self.update_progress(0)
        return False

    def on_section_clicked(self, button, section):
        """Handle section button clicks"""
        # Update button states
        for btn in [self.explore_button, self.installed_button, self.updates_button]:
            btn.get_style_context().remove_class('selected')
        button.get_style_context().add_class('selected')
        
        # Clear search entry
        self.search_entry.set_text("")
        
        # Show/hide UI elements based on section
        if section == "explore":
            # Show categories, hide update button
            self.sidebar.show()
            self.update_button.hide()
            self.search_entry.show()
            # Show all apps
            self.show_apps()
        elif section == "installed":
            # Hide categories and update button
            self.sidebar.hide()
            self.update_button.hide()
            self.search_entry.show()
            # Show installed apps
            self.show_installed_apps()
        else:  # updates
            # Hide categories, show update button
            self.sidebar.hide()
            self.update_button.show()
            self.search_entry.show()
            # Show update apps
            self.show_update_apps()

    def show_installed_apps(self):
        """Show only installed apps"""
        # Clear current content
        for child in self.app_list_box.get_children():
            self.app_list_box.remove(child)
        
        # Get installed apps
        installed_apps = [app for app in self.apps_data if app['folder_name'] in self.installed_apps]
        
        # Apply search filter if search entry has text
        search_text = self.search_entry.get_text().lower()
        if search_text:
            installed_apps = [
                app for app in installed_apps
                if search_text in app['app_name'].lower()
                or search_text in app['description'].lower()
                or any(search_text in cat.lower() for cat in app['categories'])
            ]
        
        if not installed_apps:
            # Create message for no installed apps
            message_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            message_box.set_valign(Gtk.Align.CENTER)
            message_box.set_halign(Gtk.Align.CENTER)
            
            # Add an icon
            icon = Gtk.Image.new_from_icon_name("dialog-information", Gtk.IconSize.DIALOG)
            message_box.pack_start(icon, False, False, 0)
            
            # Add message labels
            title_label = Gtk.Label()
            title_label.set_markup("<span size='larger' weight='bold'>No Apps Installed</span>")
            title_label.get_style_context().add_class('no-apps-message')
            message_box.pack_start(title_label, False, False, 0)
            
            if search_text:
                # Show search-specific message
                message = Gtk.Label()
                message.set_markup(f"No installed apps match the search: <i>{GLib.markup_escape_text(search_text)}</i>")
                message.get_style_context().add_class('no-apps-submessage')
                message_box.pack_start(message, False, False, 10)
            else:
                # Show general message with instructions
                message = Gtk.Label()
                message.set_markup(
                    "You haven't installed any apps yet.\n"
                    "Go to the <b>Explore</b> tab to discover and install apps."
                )
                message.set_justify(Gtk.Justification.CENTER)
                message.set_line_wrap(True)
                message.get_style_context().add_class('no-apps-submessage')
                message_box.pack_start(message, False, False, 10)
                
                # Add a button to go to Explore tab
                explore_button = Gtk.Button(label="Go to Explore")
                explore_button.get_style_context().add_class('suggested-action')  # Gives it a highlighted appearance
                explore_button.connect("clicked", lambda btn: self.on_section_clicked(self.explore_button, "explore"))
                explore_button.set_margin_top(10)
                message_box.pack_start(explore_button, False, False, 0)
            
            self.app_list_box.pack_start(message_box, True, True, 0)
        else:
            for app in installed_apps:
                self.add_app_card(app)
        
        self.app_list_box.show_all()

    def show_update_apps(self):
        """Show only apps with updates"""
        # Clear current content
        for child in self.app_list_box.get_children():
            self.app_list_box.remove(child)
        
        # Add apps with updates
        update_apps = [app for app in self.apps_data if app['folder_name'] in self.pending_updates]
        
        if not update_apps:
            # Create message for no updates
            message_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            message_box.set_valign(Gtk.Align.CENTER)
            message_box.set_halign(Gtk.Align.CENTER)
            
            # Add an icon
            icon = Gtk.Image.new_from_icon_name("software-update-available", Gtk.IconSize.DIALOG)
            message_box.pack_start(icon, False, False, 0)
            
            # Add message label
            message = Gtk.Label()
            message.set_markup("<span size='larger'>All apps are up to date</span>")
            message.get_style_context().add_class('no-apps-message')
            message_box.pack_start(message, False, False, 0)
            
            self.app_list_box.pack_start(message_box, True, True, 0)
        else:
            for app in update_apps:
                self.add_app_card(app)
        
        self.app_list_box.show_all()

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

def main():
    app = AppStoreApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
