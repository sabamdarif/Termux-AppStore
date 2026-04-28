#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing windsurf..."
distro_run "
check_and_delete '/opt/windsurf'
check_and_delete '/share/applications/pd_added/windsurf.desktop'
"
progress_done
