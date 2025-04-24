#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="neovim"
run_cmd="nvim"
version="termux_local_version"
app_type="native"
package_install_and_check "$package_name git"
check_and_backup "$HOME/.config/nvim"
git clone https://github.com/NvChad/starter ~/.config/nvim
