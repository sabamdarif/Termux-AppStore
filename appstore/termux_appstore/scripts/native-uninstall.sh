#!/data/data/com.termux/files/usr/bin/bash
# Generic repo-package uninstaller for native-repo catalog entries.
# See native-install.sh for the injection contract.
APPSTORE_PACKAGE_NAME="${APPSTORE_PACKAGE_NAME:?missing package name}"
progress_phase "cleanup" 0 "Removing ${APPSTORE_PACKAGE_NAME}..."
package_remove_and_check "${APPSTORE_PACKAGE_NAME}"
