#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing lximage-qt..."

package_remove_and_check "lximage-qt"

progress_done
