# SPDX-License-Identifier: GPL-3.0-or-later
"""Script execution engine with real-time progress tracking.

Extracted from ``window.py`` to keep the main window module thin.
Handles download → detect → run → progress → cleanup lifecycle
for install/uninstall/update scripts.
"""

import os
import signal
import stat
import subprocess
import threading
import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib  # type: ignore # noqa: E402

from termux_appstore.backend.script_runner import download_script
from termux_appstore.tasks.progress import PHASE_LABELS, ProgressEngine
from termux_appstore.tasks.task_manager import update_terminal


def run_script_with_progress(
    *,
    app,
    url,
    action_label,
    on_success,
    progress_bar,
    status_label,
    terminal_view,
    progress_dialog,
    get_category_cb=None,
    show_apps_cb=None,
):
    """Download and execute an install/uninstall script with real-time
    progress tracking.

    This function spawns a daemon thread that:

    1. Downloads the script via ``download_script()``.
    2. Instantiates a :class:`ProgressEngine` and auto-detects the
       script type.
    3. Runs the script with ``PROGRESS_ENABLED=1`` in the env.
    4. Routes every output line through the engine's 4-layer parser.
    5. Filters internal protocol tokens from the terminal view.
    6. Registers a GTK heartbeat timer for drift / activity mode.

    Args:
        app:              App metadata dict.
        url:              Remote URL of the install/uninstall script.
        action_label:     Human label — ``"Installing"`` / ``"Uninstalling"``.
        on_success:       Callback invoked on the main thread on success.
        progress_bar:     ``Gtk.ProgressBar`` widget.
        status_label:     ``Gtk.Label`` for status text.
        terminal_view:    ``Gtk.TextView`` for terminal output.
        progress_dialog:  ``Gtk.Dialog`` hosting the progress UI.
        get_category_cb:  Optional callable returning the selected category.
        show_apps_cb:     Optional ``show_apps(category)`` callable.
    """
    cancelled = False
    process = None
    script_file = None

    # ── Cancel handler ────────────────────────────────────────────────
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

    # ── Progress helpers ──────────────────────────────────────────────
    def update_progress(fraction, text):
        if not progress_dialog or not progress_dialog.get_window():
            return False
        status_label.set_text(text)
        progress_bar.set_fraction(fraction)
        progress_bar.set_text(f"{int(fraction * 100)}%")
        return False

    def update_phase_label(phase):
        """Update status label prefix with human-readable phase."""
        label = PHASE_LABELS.get(phase, "")
        if label:
            return label
        return ""

    # ── Worker thread ─────────────────────────────────────────────────
    def worker():
        nonlocal script_file, process

        try:
            # Derive operation type from action_label
            op = "install"
            if "uninstall" in action_label.lower():
                op = "uninstall"
            elif "updat" in action_label.lower():
                op = "update"

            # 1. Create engine
            engine = ProgressEngine(
                operation=op,
                app_type=app.get("app_type", "native"),
            )

            GLib.idle_add(
                update_progress,
                engine.current_fraction,
                engine.current_message,
            )

            # 2. Download script
            GLib.idle_add(
                lambda: update_terminal(
                    terminal_view,
                    f"Downloading {action_label.lower()} script...\n",
                )
            )
            script_file = download_script(url)
            if not script_file or cancelled:
                if script_file and os.path.exists(script_file):
                    os.remove(script_file)
                GLib.idle_add(progress_dialog.destroy)
                return

            # 3. Auto-detect script type + advance past download phase
            try:
                with open(script_file) as f:
                    engine.detect_script_type(f.read())
            except Exception:
                pass

            engine.script_downloaded()

            GLib.idle_add(
                update_progress,
                engine.current_fraction,
                engine.current_message,
            )

            # 4. Make executable
            os.chmod(script_file, os.stat(script_file).st_mode | stat.S_IEXEC)

            # 5. Register heartbeat timer
            def heartbeat_cb():
                if cancelled or engine.is_done:
                    return False  # Stop timer
                engine.heartbeat()
                elapsed = time.time() - engine._last_token_time
                if elapsed > 10.0 and not engine.is_done:
                    # Activity mode — pulse so user knows it's not frozen
                    GLib.idle_add(progress_bar.pulse)
                else:
                    GLib.idle_add(
                        update_progress,
                        engine.current_fraction,
                        engine.current_message,
                    )
                return not engine.is_done

            GLib.timeout_add(500, heartbeat_cb)

            # 6. Run script with PROGRESS_ENABLED=1
            script_env = {**os.environ, "PROGRESS_ENABLED": "1"}

            process = subprocess.Popen(
                ["bash", script_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                preexec_fn=os.setsid,
                env=script_env,
            )

            # 7. Process output line by line
            while True:
                if cancelled:
                    GLib.idle_add(progress_dialog.destroy)
                    return

                line = process.stdout.readline() if process.stdout else ""
                if not line and process.poll() is not None:
                    break

                line_stripped = line.rstrip("\n")
                if not line_stripped:
                    continue

                fraction, message = engine.process_line(line_stripped)

                # Always update progress
                GLib.idle_add(update_progress, fraction, message)

                # Filter protocol tokens from terminal view
                if ProgressEngine.is_progress_token(line_stripped):
                    continue  # Don't show in terminal

                GLib.idle_add(lambda l=line: update_terminal(terminal_view, l))

            # 8. Finalize
            if process.wait() == 0 and not cancelled:
                GLib.idle_add(
                    update_progress,
                    0.95,
                    f"Finalizing {action_label.lower()}...",
                )
                GLib.idle_add(on_success)

                # Refresh visible app list
                if get_category_cb and show_apps_cb:
                    cat = get_category_cb()
                    GLib.idle_add(lambda c=cat: show_apps_cb(c))

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
