#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="handbrake"
version=termux_local_version
app_type="native"
# supported_distro="all"
# working_dir=""
run_cmd="ghb"

progress_phase "prepare" 0 "Preparing to install handbrake..."
package_install_and_check "handbrake"
progress_done