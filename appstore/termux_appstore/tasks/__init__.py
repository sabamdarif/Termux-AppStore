# SPDX-License-Identifier: GPL-3.0-or-later
"""Task management — progress dialogs and terminal update helpers.

Usage::

    from termux_appstore.tasks import (
        create_progress_dialog,
        update_terminal,
        parse_progress_line,
    )
"""

from termux_appstore.tasks.task_manager import (
    create_progress_dialog,
    parse_progress_line,
    update_terminal,
)

__all__ = [
    "create_progress_dialog",
    "update_terminal",
    "parse_progress_line",
]
