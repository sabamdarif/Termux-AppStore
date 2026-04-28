#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="atril"
run_cmd="atril"
version=termux_local_version
app_type="native"

progress_phase "prepare" 0 "Preparing to install atril..."
package_install_and_check "atril"
progress_done
