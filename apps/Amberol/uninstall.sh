#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing amberol..."
package_remove_and_check "amberol"
progress_done
