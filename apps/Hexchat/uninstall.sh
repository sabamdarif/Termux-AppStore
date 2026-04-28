#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing hexchat..."

package_remove_and_check "hexchat"

progress_done
