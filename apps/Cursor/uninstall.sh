#!/data/data/com.termux/files/usr/bin/bash

distro_run "
check_and_delete '${distro_path}/opt/cursor'
check_and_delete '$PREFIX/share/applications/pd_added/cursor.desktop'
"