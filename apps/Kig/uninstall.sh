#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing kig..."
package_remove_and_check "kig"
progress_done
