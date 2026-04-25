#!/data/data/com.termux/files/usr/bin/bash

pd_package_remove_and_check "code"
check_and_delete "$TERMUX_PREFIX/share/applications/code.desktop"
