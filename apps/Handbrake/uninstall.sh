#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing handbrake..."

package_remove_and_check "handbrake"

progress_done
