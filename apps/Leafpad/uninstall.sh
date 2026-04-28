#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing leafpad..."

package_remove_and_check "leafpad"

progress_done
