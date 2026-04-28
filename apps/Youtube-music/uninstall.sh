#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing youtube-music..."
pd_check_and_delete "/opt/AppImageLauncher/youtube-music"
check_and_delete "${TERMUX_PREFIX}/share/applications/pd_added/youtube-music.desktop"
progress_done
