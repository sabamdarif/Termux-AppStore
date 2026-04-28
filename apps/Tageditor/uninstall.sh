#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing tageditor..."

package_remove_and_check "tageditor"

progress_done
