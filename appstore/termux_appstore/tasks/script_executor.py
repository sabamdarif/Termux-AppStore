# SPDX-License-Identifier: GPL-3.0-or-later
"""Script execution engine with real-time progress tracking.

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
from gi.repository import GLib, Gtk  # type: ignore # noqa: E402

from termux_appstore.backend.script_runner import download_script
from termux_appstore.tasks.progress import PHASE_LABELS, ProgressEngine
from termux_appstore.tasks.task_manager import update_terminal


def _show_failure(progress_dialog, action_label, log_lines, exit_code, reason):
    """Switch the progress dialog into a persistent error state on the main
    thread, showing the full accumulated log with a working Save button.

    The dialog is NOT destroyed — the user reads/saves the log and closes it.
    """
    full_log = "\n".join(log_lines)

    def _apply():
        setter = getattr(progress_dialog, "appstore_set_error", None)
        if setter:
            setter(action_label, full_log, exit_code, reason)
        return False

    GLib.idle_add(_apply)


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
    refresh_view_cb=None,
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
        refresh_view_cb:  Optional callable that refreshes the current view.
    """
    cancelled = False
    process = None
    script_file = None
    log_lines = []

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

    def update_progress(fraction, text):
        if not progress_dialog or not progress_dialog.get_window():
            return False
        status_label.set_text(text)
        progress_bar.set_fraction(fraction)
        progress_bar.set_text(f"{int(fraction * 100)}%")

        cancel_btn = progress_dialog.get_widget_for_response(Gtk.ResponseType.CANCEL)
        if cancel_btn:
            cancel_btn.set_sensitive(fraction > 0.8)
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
            op = "install"
            if "uninstall" in action_label.lower():
                op = "uninstall"
            elif "updat" in action_label.lower():
                op = "update"

            engine = ProgressEngine(
                operation=op,
                app_type=app.get("app_type", "native"),
            )

            GLib.idle_add(
                update_progress,
                engine.current_fraction,
                engine.current_message,
            )

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

            os.chmod(script_file, os.stat(script_file).st_mode | stat.S_IEXEC)

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

                # Keep the full transcript in memory so it survives dialog
                # destruction and can be shown/saved on failure.
                log_lines.append(line_stripped)

                fraction, message = engine.process_line(line_stripped)

                GLib.idle_add(update_progress, fraction, message)

                if ProgressEngine.is_progress_token(line_stripped):
                    continue  # Don't show in terminal

                GLib.idle_add(lambda ln=line: update_terminal(terminal_view, ln))

            exit_code = process.wait()

            # Success requires ALL of: clean exit, an explicit __DONE__ token,
            # no __ERROR__ token, and not cancelled. Exit code alone is not
            # trusted — a script can exit 0 after a tolerated sub-failure.
            succeeded = (
                exit_code == 0
                and engine.is_done
                and not engine.has_error
                and not cancelled
            )

            if cancelled:
                GLib.idle_add(progress_dialog.destroy)
                return

            if succeeded:
                GLib.idle_add(
                    update_progress,
                    0.95,
                    f"Finalizing {action_label.lower()}...",
                )
                GLib.idle_add(on_success)

                if refresh_view_cb:
                    GLib.idle_add(refresh_view_cb)

                GLib.idle_add(update_progress, 1.0, f"{action_label} complete!")
                time.sleep(2)
                GLib.idle_add(progress_dialog.destroy)
            else:
                reason = engine.current_message if engine.has_error else ""
                _show_failure(
                    progress_dialog,
                    action_label,
                    log_lines,
                    exit_code,
                    reason,
                )
                # Do NOT destroy — leave the dialog open so the user can read
                # and save the full log.

        except Exception as e:
            print(f"{action_label} error: {e}")
            log_lines.append(f"\n[appstore] Unexpected error: {e}")
            _show_failure(progress_dialog, action_label, log_lines, None, str(e))
            # Leave the dialog open with the accumulated log.

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
