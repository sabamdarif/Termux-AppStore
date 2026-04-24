#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point for Termux AppStore.

Usage::

    python3 -m termux_appstore.main
"""

import sys

from termux_appstore.application import AppStoreApplication


def main():
    """Launch the application."""
    app = AppStoreApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
