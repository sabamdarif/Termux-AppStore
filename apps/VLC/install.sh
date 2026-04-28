#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="vlc"
version=termux_local_version
app_type="native"
supported_distro="all"
run_cmd="vlc"


progress_phase "prepare" 0 "Preparing to install vlc..."
package_install_and_check "vlc-qt"
progress_done
