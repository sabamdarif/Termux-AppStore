# SPDX-License-Identifier: GPL-3.0-or-later
"""Terminal emulator components — ANSI parser, emulator widget, command runner.

Usage::

    from termux_appstore.terminal import (
        AnsiColorParser,
        TerminalEmulator,
        CommandRunner,
        CommandOutputWindow,
        create_terminal_widget,
        show_command_output,
    )
"""

from termux_appstore.terminal.ansi_parser import AnsiColorParser
from termux_appstore.terminal.command_runner import (
    CommandOutputWindow,
    CommandRunner,
    TerminalWindow,
    apply_terminal_css,
    create_terminal_widget,
    show_command_output,
)
from termux_appstore.terminal.emulator import TerminalEmulator

__all__ = [
    "AnsiColorParser",
    "TerminalEmulator",
    "CommandRunner",
    "CommandOutputWindow",
    "TerminalWindow",
    "apply_terminal_css",
    "create_terminal_widget",
    "show_command_output",
]
