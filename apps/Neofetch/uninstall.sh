#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing neofetch..."

package_remove_and_check "neofetch" || exit 1

progress_done

