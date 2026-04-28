#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing dosbox..."

package_remove_and_check "dosbox"

progress_done
