#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing extension-manager..."

package_remove_and_check "extension-manager"

progress_done
