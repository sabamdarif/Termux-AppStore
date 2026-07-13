# SPDX-License-Identifier: GPL-3.0-or-later
"""Install/uninstall script download and modification.

Downloads app scripts from GitHub, injects the ``inbuild_functions``
source line after the shebang, and returns the local path.
"""

import os
import subprocess
import time
from pathlib import Path

from termux_appstore._buildconf import PREFIX
from termux_appstore.constants import TERMUX_PREFIX, TERMUX_TMP


def modify_script(script_path):
    """Prepare a downloaded script for reliable execution.

    Inserts, right after the shebang: ``set -Eeo pipefail``, a ``source``
    of the shared ``inbuild_functions`` library, and ``__appstore_begin``
    (which arms the ERR trap). Appends ``__appstore_end`` at EOF so a clean
    run emits ``__DONE__`` and any failure emits ``__ERROR__`` + non-zero
    exit.

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

        # Resolve inbuild_functions path with multiple fallbacks.
        # 3. PREFIX-based:     <PREFIX>/lib/python*/site-packages/termux_appstore/inbuild_functions/
        pkg_root = Path(__file__).resolve().parent.parent  # termux_appstore/
        candidates = [
            pkg_root / "inbuild_functions" / "inbuild_functions",
            pkg_root.parent / "inbuild_functions" / "inbuild_functions",
        ]

        # PREFIX-based fallback — glob for the python version directory
        prefix_site = Path(PREFIX) / "lib"
        if prefix_site.exists():
            for pydir in sorted(
                prefix_site.glob("python*/site-packages"), reverse=True
            ):
                candidates.append(
                    pydir
                    / "termux_appstore"
                    / "inbuild_functions"
                    / "inbuild_functions"
                )
                break

        inbuild_functions_path = None
        for candidate in candidates:
            if candidate.exists():
                inbuild_functions_path = candidate
                break

        if inbuild_functions_path is None:
            print("Error: inbuild_functions not found. Searched:")
            for c in candidates:
                print(f"  - {c}")
            return False

        for shebang in [
            f"#!{TERMUX_PREFIX}/bin/bash\n",
            "#!/bin/bash\n",
        ]:
            if shebang in content:
                # After the shebang: enable strict mode, source the shared
                # library, then arm the failure trap. `set -Eeo pipefail`
                # (deliberately NOT -u, to avoid breaking scripts that
                # reference maybe-unset vars) makes any unhandled command
                # failure abort the script; the ERR trap emits __ERROR__ and
                # exits non-zero. __appstore_end at EOF emits __DONE__ only on
                # a clean run, so the app store never falsely reports success.
                header = (
                    f"{shebang}"
                    "set -Eeo pipefail\n"
                    f"source {inbuild_functions_path}\n"
                    "__appstore_begin\n"
                )
                new_content = content.replace(shebang, header, 1)
                if not new_content.endswith("\n"):
                    new_content += "\n"
                new_content += "__appstore_end\n"
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
