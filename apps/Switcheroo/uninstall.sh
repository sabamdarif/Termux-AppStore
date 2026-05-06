#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing switcheroo..."
package_remove_and_check "switcheroo"
progress_done
