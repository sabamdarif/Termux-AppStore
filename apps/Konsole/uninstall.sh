#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing konsole..."

package_remove_and_check "konsole"

progress_done
