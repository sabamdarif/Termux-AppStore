#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing luanti..."

package_remove_and_check "luanti"

progress_done
