#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing git-gui..."

package_remove_and_check "git-gui"

progress_done
