#!/data/data/com.termux/files/usr/bin/bash

package_remove_and_check "neovim"
check_and_delete "$HOME/.config/nvim"
check_and_delete "$HOME/.local/state/nvim"
check_and_delete "$HOME/.local/share/nvim"
