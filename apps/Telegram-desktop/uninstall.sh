#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing telegram-desktop..."

package_remove_and_check "telegram-desktop"

progress_done
