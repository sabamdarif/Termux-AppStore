#!/data/data/com.termux/files/usr/bin/bash

package_remove_and_check "yad"
check_and_delete "$HOME/.local/bin/yt-dlp-gui"
check_and_delete "$HOME/.config/ytdlp-gui/"
check_and_delete "${TERMUX_PREFIX}/share/applications/ytdlp-gui.desktop"
