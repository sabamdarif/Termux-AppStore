#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing cursor..."

pd_package_remove_and_check "cursor"
check_and_delete "${TERMUX_PREFIX}/share/applications/pd_added/cursor.desktop"

progress_done
