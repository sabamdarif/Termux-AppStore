#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing fastfetch..."

package_remove_and_check "fastfetch"

progress_done

