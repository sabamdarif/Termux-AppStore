#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing obsidian..."
check_and_delete "${distro_path}/opt/AppImageLauncher/Obsidian"
check_and_delete "${distro_path}/usr/share/icons/hicolor/*/apps/obsidian.png"
check_and_delete "${TERMUX_PREFIX}/share/applications/pd_added/obsidian.desktop"
progress_done
