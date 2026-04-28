#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing freetube..."
check_and_delete "${distro_path}/opt/AppImageLauncher/"
check_and_delete "${distro_path}/usr/share/icons/hicolor/*/apps/.png"
check_and_delete "${TERMUX_PREFIX}/share/applications/pd_added/.desktop"
progress_done
