#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing termux-dm..."
package_remove_and_check "termux-dm"
progress_done
