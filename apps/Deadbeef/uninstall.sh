#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing deadbeef..."

package_remove_and_check "deadbeef"

progress_done
