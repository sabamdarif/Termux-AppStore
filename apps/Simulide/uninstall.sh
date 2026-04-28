#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing simulide..."

package_remove_and_check "simulide"

progress_done
