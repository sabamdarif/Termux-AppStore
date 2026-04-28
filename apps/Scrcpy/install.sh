#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="scrcpy"
version=termux_local_version
app_type="native"
# supported_distro="all"
# working_dir=""
# run_cmd="scrcpy"

progress_phase "prepare" 0 "Preparing to install scrcpy..."
package_install_and_check "scrcpy"
progress_done