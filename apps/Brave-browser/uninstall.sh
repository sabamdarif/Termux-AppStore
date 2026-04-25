#!/data/data/com.termux/files/usr/bin/bash

pd_check_and_delete '/opt/brave-browser'
pd_check_and_delete '/share/applications/pd_added/brave-browser.desktop'
check_and_delete "${PREFIX}/share/applications/pd_added/brave-browser.desktop"
