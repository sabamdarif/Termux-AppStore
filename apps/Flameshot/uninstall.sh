#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing flameshot..."

package_remove_and_check "flameshot"

progress_done
