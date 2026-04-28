#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing abiword..."

package_remove_and_check "abiword"

progress_done
