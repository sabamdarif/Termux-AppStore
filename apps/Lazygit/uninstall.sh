#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing lazygit..."

package_remove_and_check "lazygit"

progress_done
