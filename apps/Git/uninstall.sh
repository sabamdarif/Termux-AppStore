#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing git..."

package_remove_and_check "git"

progress_done

