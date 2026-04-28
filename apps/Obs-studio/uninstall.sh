#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing obs-studio..."
package_remove_and_check "obs-studio"
progress_done
