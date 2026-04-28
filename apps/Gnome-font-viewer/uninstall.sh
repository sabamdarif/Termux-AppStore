#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing gnome-font-viewer..."

package_remove_and_check "gnome-font-viewer"

progress_done
