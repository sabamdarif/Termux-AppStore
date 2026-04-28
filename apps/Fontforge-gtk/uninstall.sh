#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing fontforge-gtk..."

package_remove_and_check "fontforge-gtk"

progress_done
