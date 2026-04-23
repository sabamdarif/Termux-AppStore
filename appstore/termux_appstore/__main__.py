#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Allow running the package as ``python3 -m termux_appstore``."""

import sys

from termux_appstore.main import main

sys.exit(main())
