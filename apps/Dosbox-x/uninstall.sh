#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing dosbox-x..."

package_remove_and_check "dosbox-x"

progress_done
