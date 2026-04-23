# SPDX-License-Identifier: GPL-3.0-or-later
"""Install/uninstall script download and modification.

Downloads app scripts from GitHub, injects the ``inbuild_functions``
source line after the shebang, and returns the local path.
"""

import os
import subprocess
import time
from pathlib import Path

from termux_appstore.constants import TERMUX_TMP


def modify_script(script_path):
    """Inject ``source inbuild_functions`` after the shebang line.

    Supports both ``#!/data/data/com.termux/files/usr/bin/bash`` and
    ``#!/bin/bash`` shebangs.

    Args:
        script_path: Absolute path to the downloaded script.

    Returns:
        bool: ``True`` on success.
    """
    try:
        with open(script_path, "r") as f:
            content = f.read()

        # Resolve the inbuild_functions path relative to the project root.
        # In the installed layout the project root is the parent of
        # ``termux_appstore/``, which mirrors the repo root where
        # ``inbuild_functions/inbuild_functions`` lives.
        project_root = Path(__file__).resolve().parent.parent.parent
        inbuild_functions_path = (
            project_root / "inbuild_functions" / "inbuild_functions"
        )

        for shebang in [
            "#!/data/data/com.termux/files/usr/bin/bash\n",
            "#!/bin/bash\n",
        ]:
            if shebang in content:
                new_content = content.replace(
                    shebang, f"{shebang}source {inbuild_functions_path}\n"
                )
                with open(script_path, "w") as f:
                    f.write(new_content)
                return True

        print("No compatible shebang found in script")
        return False

    except Exception as e:
        print(f"Error injecting common_functions source: {e}")
        return False


def download_script(url):
    """Download a script from *url* and prepare it for execution.

    Uses ``aria2c`` for the download, verifies encoding, and injects
    the ``inbuild_functions`` source line.

    Args:
        url: Remote URL of the install/uninstall script.

    Returns:
        str | None: Local path to the ready-to-run script, or ``None``
        on failure.
    """
    script_path = None
    try:
        os.makedirs(TERMUX_TMP, exist_ok=True)

        script_name = f"appstore_{int(time.time())}.sh"
        script_path = os.path.join(TERMUX_TMP, script_name)

        print(f"Downloading script from {url} to {script_path}")
        command = f"aria2c -x 16 -s 16 '{url}' -d '{TERMUX_TMP}' -o '{script_name}'"
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, encoding="utf-8"
        )

        if result.returncode != 0:
            print(f"Download failed: {result.stderr}")
            return None

        if not os.path.exists(script_path):
            print("Script file not found after download")
            return None

        # Verify the file is valid UTF-8
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                f.read()
        except UnicodeDecodeError:
            print("Script file has invalid encoding")
            if os.path.exists(script_path):
                os.remove(script_path)
            return None

        if not modify_script(script_path):
            print("Failed to modify script")
            return None

        return script_path
    except Exception as e:
        print(f"Error downloading script: {e}")
        if script_path and os.path.exists(script_path):
            os.remove(script_path)
        return None
