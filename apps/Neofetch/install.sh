#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="neofetch"
version=termux_local_version
app_type="native"

progress_phase "prepare" 0 "Preparing to install neofetch..."
package_install_and_check "$package_name" || exit 1
progress_done

