#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="dconf-editor"
run_cmd="dconf-editor"
version="termux_local_version"
app_type="native"
progress_phase "prepare" 0 "Preparing to install dconf-editor..."
package_install_and_check "$package_name"
progress_done
