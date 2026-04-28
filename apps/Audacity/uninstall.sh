#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing audacity..."

package_remove_and_check "audacity"

progress_done

