# SPDX-License-Identifier: GPL-3.0-or-later
"""Progress dialog and task management.

Provides ``create_progress_dialog`` — a rich progress/terminal dialog
for install, uninstall, and update operations — plus the
``update_terminal`` helper used across the app.
"""

import os
from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # type: ignore # noqa: E402

from termux_appstore.terminal.ansi_parser import AnsiColorParser
from termux_appstore.terminal.command_runner import create_terminal_widget
from termux_appstore.terminal.emulator import TerminalEmulator

# ---------------------------------------------------------------------------
# Terminal text helper
# ---------------------------------------------------------------------------


def update_terminal(terminal_view, text, log_state=None):
    """Update a terminal view with new text and optionally write to a log.

    Args:
        terminal_view: A ``Gtk.TextView`` that may have a
            ``terminal_emulator`` attribute attached.
        text: The text to append.
        log_state: Optional dict ``{"active": bool, "file": file_obj,
            "path": str}`` for continuous logging.  Pass ``None`` to
            skip logging.
    """
    if not text:
        return

    # Ensure the terminal_emulator is attached
    if not hasattr(terminal_view, "terminal_emulator"):
        terminal_view.terminal_emulator = TerminalEmulator(terminal_view)

    if terminal_view.terminal_emulator:
        terminal_view.terminal_emulator.append_text(text)

    # Continuous log file
    if log_state and log_state.get("active") and log_state.get("file"):
        try:
            clean_text = AnsiColorParser().strip_ansi(text)
            log_state["file"].write(clean_text)
            log_state["file"].flush()
        except Exception as e:
            try:
                terminal_view.terminal_emulator.append_text(
                    f"\nError writing to log file: {e}\nLogging disabled.\n"
                )
                log_state["file"].close()
            except Exception:
                pass
            log_state["file"] = None
            log_state["active"] = False
            log_state["path"] = None


# ---------------------------------------------------------------------------
# Progress dialog factory
# ---------------------------------------------------------------------------


def create_progress_dialog(
    parent,
    title="Installing...",
    allow_cancel=True,
    use_terminal_default=False,
):
    """Create an enhanced progress dialog with terminal integration.

    Args:
        parent: Transient parent window.
        title: Dialog title.
        allow_cancel: Whether to include a Cancel button.
        use_terminal_default: Start in terminal view.

    Returns:
        tuple: ``(dialog, status_label, progress_bar, terminal_view,
        terminal_emulator, log_state)``
    """
    # Mutable log state shared across closures
    log_state = {"active": False, "file": None, "path": None}

    dialog = Gtk.Dialog(
        title=title, parent=parent, modal=True, destroy_with_parent=True
    )

    # Header bar
    header_bar = Gtk.HeaderBar()
    header_bar.set_show_close_button(False)
    header_bar.set_title(title)

    terminal_button = Gtk.Button.new_from_icon_name(
        "utilities-terminal-symbolic", Gtk.IconSize.BUTTON
    )
    terminal_button.set_tooltip_text("Toggle Terminal View")
    terminal_button.get_style_context().add_class("suggested-action")
    header_bar.pack_end(terminal_button)

    save_button = Gtk.Button.new_from_icon_name(
        "document-save-symbolic", Gtk.IconSize.BUTTON
    )
    save_button.set_tooltip_text("Save Log to File")
    header_bar.pack_end(save_button)

    log_control_button = Gtk.Button.new_from_icon_name(
        "media-record-symbolic", Gtk.IconSize.BUTTON
    )
    log_control_button.set_tooltip_text("Start Continuous Logging")
    log_control_button.get_style_context().add_class("destructive-action")
    header_bar.pack_end(log_control_button)

    dialog.set_titlebar(header_bar)

    if allow_cancel:
        cancel_btn = dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        cancel_btn.get_style_context().add_class("destructive-action")

    # Stack: progress vs terminal
    stack = Gtk.Stack()
    stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
    stack.set_transition_duration(150)

    # ---- Progress view ----
    progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    progress_box.set_margin_start(10)
    progress_box.set_margin_end(10)
    progress_box.set_margin_top(10)
    progress_box.set_margin_bottom(10)

    status_label = Gtk.Label()
    status_label.set_line_wrap(True)
    status_label.set_line_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    status_label.set_justify(Gtk.Justification.LEFT)
    status_label.set_halign(Gtk.Align.START)
    status_label.set_text("Starting...")

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scroll.set_size_request(-1, 60)
    scroll.add(status_label)
    progress_box.pack_start(scroll, True, True, 0)

    progress_bar = Gtk.ProgressBar()
    progress_bar.set_show_text(True)
    progress_bar.set_size_request(-1, 20)
    progress_bar.get_style_context().add_class("custom-progress")
    progress_box.pack_start(progress_bar, False, True, 0)

    # ---- Terminal view ----
    terminal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    terminal_box.set_margin_start(10)
    terminal_box.set_margin_end(10)
    terminal_box.set_margin_top(10)
    terminal_box.set_margin_bottom(10)

    terminal_scroll, terminal_emulator, _ = create_terminal_widget()
    terminal_scroll.set_size_request(450, 200)
    terminal_scroll.set_vexpand(True)
    terminal_scroll.set_hexpand(True)

    terminal_view = terminal_emulator.text_view

    terminal_box.pack_start(terminal_scroll, True, True, 0)

    # Clear button under terminal
    terminal_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    terminal_btn_box.set_halign(Gtk.Align.END)
    terminal_btn_box.set_margin_top(5)

    clear_button = Gtk.Button()
    clear_icon = Gtk.Image.new_from_icon_name(
        "edit-clear-symbolic", Gtk.IconSize.SMALL_TOOLBAR
    )
    clear_button.set_image(clear_icon)
    clear_button.set_tooltip_text("Clear Terminal")
    clear_button.connect("clicked", lambda b: terminal_emulator.clear())
    terminal_btn_box.pack_end(clear_button, False, False, 0)
    terminal_box.pack_start(terminal_btn_box, False, False, 0)

    stack.add_named(progress_box, "progress")
    stack.add_named(terminal_box, "terminal")

    initial_view = "terminal" if use_terminal_default else "progress"
    stack.set_visible_child_name(initial_view)

    if use_terminal_default:
        terminal_button.get_style_context().remove_class("suggested-action")

    terminal_button.set_tooltip_text(
        "Show Progress" if use_terminal_default else "Show Terminal"
    )

    content_area = dialog.get_content_area()
    content_area.add(stack)

    dialog.set_resizable(True)
    dialog.set_default_size(500, 300)

    # ---- Toggle handler ----
    def _toggle_terminal(button):
        current = stack.get_visible_child_name()
        new_view = "terminal" if current == "progress" else "progress"
        stack.set_visible_child_name(new_view)

        if new_view == "terminal":
            button.set_tooltip_text("Show Progress")
            button.get_style_context().remove_class("suggested-action")
        else:
            button.set_tooltip_text("Show Terminal")
            button.get_style_context().add_class("suggested-action")

    terminal_button.connect("clicked", _toggle_terminal)

    # ---- Response handler (log cleanup) ----
    def _on_response(dlg, response_id):
        if log_state["active"] and log_state["file"]:
            try:
                log_state["file"].write("\n--- Operation completed or cancelled ---\n")
                log_state["file"].close()
            except Exception:
                pass
            log_state["file"] = None
            log_state["active"] = False
            log_state["path"] = None

    dialog.connect("response", _on_response)

    # ---- Save log handler ----
    def _on_save_log(button):
        buf = terminal_view.get_buffer()
        start_iter, end_iter = buf.get_bounds()
        text = buf.get_text(start_iter, end_iter, False)

        file_dialog = Gtk.FileChooserDialog(
            title="Save Log File",
            parent=dialog,
            action=Gtk.FileChooserAction.SAVE,
        )
        file_dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE,
            Gtk.ResponseType.OK,
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_dialog.set_current_name(f"appstore_log_{timestamp}.txt")

        response = file_dialog.run()
        if response == Gtk.ResponseType.OK:
            filename = file_dialog.get_filename()
            try:
                clean_text = AnsiColorParser().strip_ansi(text)
                with open(filename, "w") as f:
                    f.write(clean_text)
                current_text = status_label.get_text()
                status_label.set_text(f"{current_text}\nLog saved to: {filename}")
            except Exception as e:
                terminal_emulator.append_text(f"\nError saving log: {e}\n")
        file_dialog.destroy()

    save_button.connect("clicked", _on_save_log)

    # ---- Continuous log handler ----
    def _on_log_control(button):
        if log_state["active"] and log_state["file"]:
            # Stop logging
            try:
                log_state["file"].write("\n--- Logging stopped ---\n")
                log_state["file"].close()
            except Exception:
                pass
            log_state["file"] = None
            log_state["active"] = False

            button.set_tooltip_text("Start Continuous Logging")
            button.set_image(
                Gtk.Image.new_from_icon_name(
                    "media-record-symbolic", Gtk.IconSize.BUTTON
                )
            )
            button.get_style_context().add_class("destructive-action")
            button.get_style_context().remove_class("suggested-action")
            terminal_emulator.append_text("\n--- Continuous logging stopped ---\n")
        else:
            # Start logging — pick file
            file_dialog = Gtk.FileChooserDialog(
                title="Save Continuous Log",
                parent=dialog,
                action=Gtk.FileChooserAction.SAVE,
            )
            file_dialog.add_buttons(
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_SAVE,
                Gtk.ResponseType.OK,
            )
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_dialog.set_current_name(f"appstore_continuous_log_{timestamp}.txt")

            response = file_dialog.run()
            if response == Gtk.ResponseType.OK:
                log_state["path"] = file_dialog.get_filename()
                try:
                    log_state["file"] = open(log_state["path"], "w")
                    log_state["file"].write(
                        f"--- Continuous logging started at "
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n\n"
                    )
                    log_state["active"] = True

                    button.set_tooltip_text("Stop Continuous Logging")
                    button.set_image(
                        Gtk.Image.new_from_icon_name(
                            "media-playback-stop-symbolic", Gtk.IconSize.BUTTON
                        )
                    )
                    button.get_style_context().remove_class("destructive-action")
                    button.get_style_context().add_class("suggested-action")
                    terminal_emulator.append_text(
                        f"\n--- Continuous logging started - "
                        f"saving to {log_state['path']} ---\n"
                    )
                except Exception as e:
                    terminal_emulator.append_text(
                        f"\n--- Error setting up logging: {e} ---\n"
                    )
                    log_state["file"] = None
                    log_state["active"] = False
            file_dialog.destroy()

    log_control_button.connect("clicked", _on_log_control)

    dialog.show_all()

    return (
        dialog,
        status_label,
        progress_bar,
        terminal_view,
        terminal_emulator,
        log_state,
    )


# ---------------------------------------------------------------------------
# Progress parsing helper
# ---------------------------------------------------------------------------


def parse_progress_line(line):
    """Parse a ``PROGRESS:type:value:message`` line.

    Returns:
        dict | None: ``{"type", "value", "message"}`` or ``None``.
    """
    if line.startswith("PROGRESS:"):
        parts = line[9:].split(":", 2)
        if len(parts) >= 2:
            return {
                "type": parts[0],
                "value": parts[1],
                "message": parts[2] if len(parts) > 2 else "",
            }
    return None
