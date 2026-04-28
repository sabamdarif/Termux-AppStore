#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing eog..."

package_remove_and_check "eog"

progress_done
