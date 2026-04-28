#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing neovim..."

package_remove_and_check "neovim"

progress_done
