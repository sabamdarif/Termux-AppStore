#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="audiotube"
run_cmd="audiotube"
version="termux_local_version"
app_type="native"
progress_phase "prepare" 0 "Preparing to install audiotube..."
package_install_and_check "$package_name kf6-kitemmodels"
progress_done
