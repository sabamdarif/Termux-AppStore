#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="termux-dm"
run_cmd="wget https://raw.githubusercontent.com/Superchavo/termux-display-manager-repo/refs/heads/master/tdmautoinstall.sh && chmod +x ./tdmautoinstall.sh && ./tdmautoinstall.sh"
version="5.0"
app_type="native"
progress_phase "prepare" 0 "Preparing to install..."
package_install_and_check "$package_name"
progress_done
