#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="kvantum"
run_cmd="kvantummanager"
version=termux_local_version
app_type="native"

progress_phase "prepare" 0 "Preparing to install kvantum..."
package_install_and_check "kvantum"
progress_done
