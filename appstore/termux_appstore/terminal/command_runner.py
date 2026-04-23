# SPDX-License-Identifier: GPL-3.0-or-later
"""Command runner, terminal window, and command output window.

Provides ``CommandRunner`` for pty-based command execution,
``TerminalWindow`` for a standalone terminal demo, and
``CommandOutputWindow`` for displaying command output in a popup.
"""

import fcntl
import os
import pty
import signal
import struct
import subprocess
import termios
import threading
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # type: ignore # noqa: E402

from termux_appstore.terminal.emulator import TerminalEmulator
from termux_appstore.constants import TERMUX_PREFIX

# ---------------------------------------------------------------------------
# CSS helpers
# ---------------------------------------------------------------------------


def find_terminal_css_path():
    """Find the terminal CSS file path with fallback options."""
    possible_paths = [
        # Inside the package (meson-installed)
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "style",
            "terminal_style.css",
        ),
        # Termux-specific path (legacy)
        os.path.join(TERMUX_PREFIX, "opt", "appstore", "style", "terminal_style.css"),
    ]

    for path in possible_paths:
        resolved = os.path.normpath(path)
        if os.path.isfile(resolved):
            print(f"Found terminal CSS at: {resolved}")
            return resolved

    default_path = os.path.normpath(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "style",
            "terminal_style.css",
        )
    )
    print(f"Terminal CSS not found, using default path: {default_path}")
    return default_path


TERMINAL_CSS_PATH = find_terminal_css_path()


def apply_terminal_css(widget):
    """Apply terminal CSS styles to a widget."""
    css_provider = Gtk.CssProvider()

    try:
        css_provider.load_from_path(TERMINAL_CSS_PATH)
        print(f"Successfully loaded terminal CSS from {TERMINAL_CSS_PATH}")
    except Exception as e:
        print(f"Could not load terminal CSS from {TERMINAL_CSS_PATH}: {e}")
        print("Using fallback inline CSS")
        css_provider.load_from_data(b"""
        .terminal-view {
            background-color: #282c34;
            color: #abb2bf;
            font-family: monospace;
            padding: 8px;
        }
        .terminal-window {
            background-color: #21252b;
        }
        .run-button {
            background-color: #98c379;
            color: #282c34;
        }
        .clear-button {
            background-color: #e06c75;
            color: #282c34;
        }
        """)

    style_context = widget.get_style_context()
    style_context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


# ---------------------------------------------------------------------------
# Widget factory
# ---------------------------------------------------------------------------


def create_terminal_widget():
    """Create a scrolled window with a terminal view ready to use.

    Returns:
        tuple: ``(scrolled_window, terminal_emulator, command_runner)``
    """
    scrolled_window = Gtk.ScrolledWindow()
    scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrolled_window.set_hexpand(True)
    scrolled_window.set_vexpand(True)

    terminal_view = Gtk.TextView()
    terminal_view.set_editable(False)
    terminal_view.set_cursor_visible(False)
    terminal_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    terminal_view.get_style_context().add_class("terminal-view")
    scrolled_window.add(terminal_view)

    terminal_emulator = TerminalEmulator(terminal_view)
    command_runner = CommandRunner(terminal_emulator)

    return scrolled_window, terminal_emulator, command_runner


# ---------------------------------------------------------------------------
# CommandRunner
# ---------------------------------------------------------------------------


class CommandRunner:
    """Run shell commands and display output in a terminal."""

    def __init__(self, terminal):
        self.terminal = terminal
        self.process = None
        self.is_running = False
        self.master_fd = None
        self.slave_fd = None
        self.io_watch_id = None
        self.final_output_received = False
        self.output_buffer = bytearray()

    def run_command(self, command, on_complete=None):
        """Run a shell command and display its output in the terminal.

        Args:
            command: Shell command string to execute.
            on_complete: Optional callback ``(return_code: int) -> None``.

        Returns:
            bool: ``True`` when the command was started successfully.
        """
        if self.is_running:
            self.terminal.append_text(
                "A command is already running. Please wait for it to complete.\n"
            )
            return False

        self.is_running = True
        self.final_output_received = False
        self.output_buffer = bytearray()
        self.terminal.append_text(f"Running: {command}\n\n")

        try:
            # Create a pseudo-terminal for interactive commands
            self.master_fd, self.slave_fd = pty.openpty()

            # Configure terminal size
            fcntl.ioctl(
                self.slave_fd, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0)
            )

            # Make the master fd non-blocking
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            # Set up environment
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"
            env["COLUMNS"] = "80"
            env["LINES"] = "24"
            env["APT_FORCE_CLI_PROMPT"] = "1"
            env["PYTHONUTF8"] = "1"

            self.process = subprocess.Popen(
                ["bash", "-c", command],
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                universal_newlines=False,
                env=env,
                preexec_fn=os.setsid,
            )

            # Close slave end in the parent
            os.close(self.slave_fd)
            self.slave_fd = None

            # Set up IO watch
            self.io_watch_id = GLib.io_add_watch(
                self.master_fd,
                GLib.PRIORITY_DEFAULT,
                GLib.IOCondition.IN | GLib.IOCondition.HUP,
                self._on_pty_output,
            )

            # Monitor process completion in a thread
            def monitor_process():
                if self.process is None:
                    return
                return_code = self.process.wait()
                time.sleep(0.2)
                self._flush_output_buffer()
                self.final_output_received = True
                GLib.idle_add(self._command_completed, return_code, on_complete)

            thread = threading.Thread(target=monitor_process)
            thread.daemon = True
            thread.start()

            return True

        except Exception as e:
            self.terminal.append_text(f"Error running command: {str(e)}\n")
            self._cleanup()
            return False

    def cancel(self):
        """Cancel the running command."""
        if self.is_running and self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.terminal.append_text("\nCommand terminated by user.\n")
            except Exception as e:
                self.terminal.append_text(f"\nError terminating command: {str(e)}\n")

            self._cleanup()
            return True
        return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_pty_output(self, fd, condition):
        """Handle output from the pty."""
        if condition & GLib.IOCondition.IN:
            try:
                data = os.read(fd, 4096)
                if data:
                    self.output_buffer.extend(data)
                    self._process_output_buffer()
                    return True
            except OSError:
                pass

        self._cleanup_io_watch()
        return False

    def _process_output_buffer(self):
        """Decode and display the output buffer."""
        try:
            text = self.output_buffer.decode("utf-8", errors="replace")
            GLib.idle_add(self._update_terminal, text)
            self.output_buffer = bytearray()
        except UnicodeDecodeError:
            return

    def _flush_output_buffer(self):
        """Flush any remaining data in the output buffer."""
        if self.output_buffer:
            try:
                text = self.output_buffer.decode("utf-8", errors="replace")
                GLib.idle_add(self._update_terminal, text)
                self.output_buffer = bytearray()
            except Exception:
                pass

    def _update_terminal(self, text):
        """Update the terminal with new text (called from main thread)."""
        self.terminal.append_text(text)
        return False

    def _command_completed(self, return_code, on_complete):
        """Handle command completion (called from main thread)."""
        if self.final_output_received:
            self.terminal.append_text(
                "\n\nCommand completed with return code: " + str(return_code) + "\n"
            )
            self._cleanup()

            if on_complete:
                on_complete(return_code)

        return False

    def _cleanup_io_watch(self):
        """Clean up the IO watch."""
        if self.io_watch_id is not None:
            GLib.source_remove(self.io_watch_id)
            self.io_watch_id = None

    def _cleanup(self):
        """Clean up all resources."""
        self._cleanup_io_watch()

        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None

        if self.slave_fd is not None:
            try:
                os.close(self.slave_fd)
            except OSError:
                pass
            self.slave_fd = None

        self.process = None
        self.is_running = False


# ---------------------------------------------------------------------------
# TerminalWindow (standalone demo window)
# ---------------------------------------------------------------------------


class TerminalWindow(Gtk.Window):
    """Simple terminal window for demonstration / standalone usage."""

    def __init__(self):
        Gtk.Window.__init__(self, title="Terminal Emulator")
        self.set_default_size(800, 500)

        self.load_css()
        self.get_style_context().add_class("terminal-window")

        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(main_box)

        # Command entry
        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entry_box.set_margin_start(10)
        entry_box.set_margin_end(10)
        entry_box.set_margin_top(10)

        self.command_entry = Gtk.Entry()
        self.command_entry.set_placeholder_text("Enter command...")
        self.command_entry.connect("activate", self.on_command_enter)
        entry_box.pack_start(self.command_entry, True, True, 0)

        run_button = Gtk.Button(label="Run")
        run_button.get_style_context().add_class("run-button")
        run_button.connect("clicked", self.on_command_enter)
        entry_box.pack_start(run_button, False, False, 0)

        clear_button = Gtk.Button(label="Clear")
        clear_button.get_style_context().add_class("clear-button")
        clear_button.connect("clicked", self.on_clear_clicked)
        entry_box.pack_start(clear_button, False, False, 0)

        main_box.pack_start(entry_box, False, False, 0)

        # Terminal view
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)
        scrolled_window.set_margin_start(10)
        scrolled_window.set_margin_end(10)
        scrolled_window.set_margin_bottom(10)

        self.terminal_view = Gtk.TextView()
        self.terminal_view.set_editable(False)
        self.terminal_view.set_cursor_visible(False)
        self.terminal_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.terminal_view.get_style_context().add_class("terminal-view")

        scrolled_window.add(self.terminal_view)
        main_box.pack_start(scrolled_window, True, True, 0)

        self.terminal = TerminalEmulator(self.terminal_view)
        self.command_runner = CommandRunner(self.terminal)

        self.terminal.append_text("Terminal Emulator Ready\n")
        self.terminal.append_text("Type a command and press Enter to execute it.\n\n")

        self.connect("key-press-event", self.on_key_press)
        self.connect("destroy", Gtk.main_quit)

    def load_css(self):
        """Load CSS from terminal_style.css."""
        css_provider = Gtk.CssProvider()
        try:
            css_file = "terminal_style.css"
            css_provider.load_from_path(css_file)
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
        except Exception as e:
            print(f"Error loading CSS: {e}")

    def on_command_enter(self, widget):
        """Handle command entry."""
        command = self.command_entry.get_text().strip()
        if command:
            self.command_runner.run_command(command)
            self.command_entry.set_text("")

    def on_clear_clicked(self, button):
        """Clear the terminal."""
        self.terminal.clear()

    def on_key_press(self, widget, event):
        """Handle key press events."""
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval == Gdk.KEY_c:
            if self.command_runner.is_running:
                self.command_runner.cancel()
            return True
        return False


# ---------------------------------------------------------------------------
# CommandOutputWindow
# ---------------------------------------------------------------------------


class CommandOutputWindow(Gtk.Window):
    """Window to display command output with terminal emulation."""

    def __init__(self, title="Command Output", parent=None):
        """Initialize the command output window.

        Args:
            title: Window title.
            parent: Parent window (optional).
        """
        Gtk.Window.__init__(self, title=title)

        if parent:
            self.set_transient_for(parent)
            self.set_destroy_with_parent(True)

        self.set_default_size(700, 500)
        self.set_border_width(10)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.get_style_context().add_class("command-output-dialog")

        apply_terminal_css(self)

        # Set window icon
        icon_name = "utilities-terminal"
        icon_theme = Gtk.IconTheme.get_default()
        if icon_theme.has_icon(icon_name):
            self.set_icon_name(icon_name)

        # Main box
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(self.main_box)

        # Terminal widget
        self.scrolled_window, self.terminal_emulator, self.command_runner = (
            create_terminal_widget()
        )
        self.main_box.pack_start(self.scrolled_window, True, True, 0)

        # Button box
        self.button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.button_box.set_halign(Gtk.Align.END)
        self.button_box.set_margin_top(12)
        self.main_box.pack_start(self.button_box, False, False, 0)

        # Clear button
        self.clear_button = Gtk.Button()
        self.clear_button.set_tooltip_text("Clear terminal output")
        clear_icon = Gtk.Image.new_from_icon_name(
            "edit-clear-symbolic", Gtk.IconSize.BUTTON
        )
        self.clear_button.set_image(clear_icon)
        self.clear_button.get_style_context().add_class("command-output-clear-button")
        self.button_box.pack_start(self.clear_button, False, False, 0)

        # Save button
        self.save_button = Gtk.Button()
        self.save_button.set_tooltip_text("Save terminal output to file")
        save_icon = Gtk.Image.new_from_icon_name(
            "document-save-symbolic", Gtk.IconSize.BUTTON
        )
        self.save_button.set_image(save_icon)
        self.save_button.get_style_context().add_class("command-output-save-button")
        self.button_box.pack_start(self.save_button, False, False, 0)

        # Connect buttons
        self.clear_button.connect("clicked", lambda b: self.terminal_emulator.clear())
        self.save_button.connect(
            "clicked", lambda b: self.terminal_emulator.save_terminal_output(self)
        )

        self.connect("delete-event", self.on_window_close)

    def run_command(self, command, app_name=None):
        """Run a command and display its output.

        Args:
            command: Shell command string.
            app_name: The name of the app (for save dialog).
        """
        self.app_name = app_name
        self.terminal_emulator.append_text(f"Running: {command}\n\n")
        self.command_runner.run_command(command)
        self.show_all()
        self.present()

    def on_window_close(self, widget, event):
        """Handle window close event."""
        if self.command_runner.is_running:
            self.command_runner.cancel()
        return False


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def show_command_output(command, app_name=None, parent=None):
    """Show a command output window and run the command.

    Args:
        command: Shell command string.
        app_name: The name of the application (for the window title).
        parent: The parent window.

    Returns:
        CommandOutputWindow: The command output window.
    """
    window = CommandOutputWindow(
        title=f"Running {app_name}" if app_name else "Command Output", parent=parent
    )
    window.run_command(command, app_name)
    return window


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------


def main():
    """Main function for standalone terminal window."""
    win = TerminalWindow()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
