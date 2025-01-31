#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="neofetch"
version=termux_local_version
app_type="native"
# supported_distro="all"
# working_dir=""
# run_cmd="neofetch"

package_install_and_check "neofetch" || exit 1