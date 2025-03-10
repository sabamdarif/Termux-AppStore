#!/data/data/com.termux/files/usr/bin/bash

distro_run "
check_and_delete '/opt/brave-browser'
check_and_delete '/share/applications/pd_added/brave-browser.desktop'
"
