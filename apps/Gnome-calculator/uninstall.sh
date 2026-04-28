#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing gnome-calculator..."

package_remove_and_check "gnome-calculator"

progress_done
