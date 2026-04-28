#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="hangover"
version=termux_local_version
app_type="native"
# supported_distro="all"
# working_dir=""
# run_cmd="wine"

progress_phase "prepare" 0 "Preparing to install hangover..."
package_install_and_check "hangover"
progress_done
