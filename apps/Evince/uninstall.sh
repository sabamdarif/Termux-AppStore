#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing evince..."

package_remove_and_check "evince"

progress_done
