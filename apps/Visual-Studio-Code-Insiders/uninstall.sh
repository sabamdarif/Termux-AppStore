#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing code-insiders..."

pd_package_remove_and_check "code-insiders"
check_and_delete "$TERMUX_PREFIX/share/applications/code-insiders.desktop"

progress_done
