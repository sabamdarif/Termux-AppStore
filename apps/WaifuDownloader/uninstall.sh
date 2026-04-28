#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing waifudownloader..."

package_remove_and_check "waifudownloader"

progress_done
