#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing librewolf..."

package_remove_and_check "librewolf"

progress_done
