#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="shotcut"
version=termux_local_version
app_type="native"
# supported_distro="all"
# working_dir=""
run_cmd="shotcut"

package_install_and_check "shotcut jack jack2 jack-example-tools"

