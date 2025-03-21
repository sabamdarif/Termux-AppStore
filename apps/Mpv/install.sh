#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="mpv-x"
run_cmd="mpv --player-operation-mode=pseudo-gui"
version="termux_local_version"
app_type="native"
package_install_and_check "$package_name"
