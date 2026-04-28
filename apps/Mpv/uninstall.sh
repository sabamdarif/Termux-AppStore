#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing mpv-x..."

package_remove_and_check "mpv-x"

progress_done
