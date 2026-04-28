#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing brave-browser..."
pd_check_and_delete '/opt/brave-browser'
pd_check_and_delete '/share/applications/pd_added/brave-browser.desktop'
check_and_delete "${TERMUX_PREFIX}/share/applications/pd_added/brave-browser.desktop"
progress_done
