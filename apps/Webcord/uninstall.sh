#!/data/data/com.termux/files/usr/bin/bash

check_and_delete "${distro_path}/opt/AppImageLauncher/webcord"
check_and_delete "${distro_path}/usr/share/icons/hicolor/*/apps/webcord.png"
check_and_delete "${TERMUX_PREFIX}/share/applications/pd_added/webcord.desktop"
