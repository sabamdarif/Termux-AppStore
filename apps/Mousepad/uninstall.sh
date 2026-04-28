#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing mousepad..."

package_remove_and_check "mousepad"

progress_done
