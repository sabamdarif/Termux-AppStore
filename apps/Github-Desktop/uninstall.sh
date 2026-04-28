#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing github-desktop..."

pd_package_remove_and_check "github-desktop"
check_and_delete "${TERMUX_PREFIX}/share/applications/github-desktop.desktop"

progress_done

