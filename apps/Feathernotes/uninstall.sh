#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing feathernotes..."

package_remove_and_check "feathernotes"

progress_done
