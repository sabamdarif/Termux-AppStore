#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing scrcpy..."

package_remove_and_check "scrcpy"

progress_done