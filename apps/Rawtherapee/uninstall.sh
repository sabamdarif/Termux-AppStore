#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing rawtherapee..."

package_remove_and_check "rawtherapee"

progress_done
