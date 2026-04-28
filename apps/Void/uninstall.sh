#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing void..."
distro_run "
check_and_delete '/opt/void'
check_and_delete '/share/applications/pd_added/void.desktop'
"
progress_done
