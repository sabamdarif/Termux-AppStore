#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing firefoxpwa..."

package_remove_and_check "firefoxpwa"

progress_done
