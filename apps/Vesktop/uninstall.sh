#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing vesktop..."

pd_package_remove_and_check "vesktop"
check_and_delete "${TERMUX_PREFIX}/share/applications/pd_added/vesktop.desktop"

progress_done
