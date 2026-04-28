#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="rhythmbox"
version=termux_local_version
app_type="native"
# supported_distro="all"
# working_dir=""
run_cmd="rhythmbox"

progress_phase "prepare" 0 "Preparing to install rhythmbox..."
package_install_and_check "rhythmbox"
progress_done