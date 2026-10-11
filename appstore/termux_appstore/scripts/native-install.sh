#!/data/data/com.termux/files/usr/bin/bash
# Generic repo-package installer for native-repo catalog entries.
# modify_script() injects set -Eeo pipefail + source inbuild_functions +
# __appstore_begin after the shebang, and appends __appstore_end at EOF —
# this script deliberately does NOT call progress_done itself.
APPSTORE_PACKAGE_NAME="${APPSTORE_PACKAGE_NAME:?missing package name}"
progress_phase "prepare" 0 "Preparing to install ${APPSTORE_PACKAGE_NAME}..."
package_install_and_check "${APPSTORE_PACKAGE_NAME}"
