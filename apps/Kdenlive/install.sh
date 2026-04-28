#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="kdenlive"
version=termux_local_version
app_type="native"
# supported_distro="all"
# working_dir=""
run_cmd="kdenlive"

progress_phase "prepare" 0 "Preparing to install kdenlive..."
package_install_and_check "kdenlive"
progress_done