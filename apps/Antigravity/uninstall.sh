#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing antigravity..."
pd_package_install_and_check "antigravity"
check_and_delete "$TERMUX_PREFIX/share/applications/antigravity.desktop"
progress_done
