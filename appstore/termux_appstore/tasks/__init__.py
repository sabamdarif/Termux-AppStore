# SPDX-License-Identifier: GPL-3.0-or-later
"""Task management — progress dialogs, terminal helpers, and progress engine.

Usage::

    from termux_appstore.tasks import (
        create_progress_dialog,
        update_terminal,
        parse_progress_line,
        ProgressEngine,
        run_script_with_progress,
    )
"""

from termux_appstore.tasks.progress import ProgressEngine
from termux_appstore.tasks.script_executor import run_script_with_progress
from termux_appstore.tasks.task_manager import (
    create_progress_dialog,
    parse_progress_line,
    update_terminal,
)

__all__ = [
    "create_progress_dialog",
    "update_terminal",
    "parse_progress_line",
    "ProgressEngine",
    "run_script_with_progress",
]
