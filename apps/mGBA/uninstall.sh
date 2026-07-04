#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing mGBA..."
pd_check_and_delete "/opt/AppImageLauncher/mGBA"
pd_check_and_delete "/usr/local/bin/mgba-appimage"
check_and_delete "${TERMUX_PREFIX}/share/applications/pd_added/mgba.desktop"
progress_done
