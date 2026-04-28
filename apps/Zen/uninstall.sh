#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing zen-browser..."
pd_check_and_delete '/opt/zen-browser'
check_and_delete "$TERMUX_PREFIX/share/applications/pd_added/zen-browser.desktop"
progress_done
