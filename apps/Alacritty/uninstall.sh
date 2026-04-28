#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing alacritty..."

package_remove_and_check "alacritty"

progress_done
