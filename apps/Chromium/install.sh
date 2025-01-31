#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="chromium"
version=termux_local_version
app_type="native"
# supported_distro="all"
# working_dir=""
run_cmd="/data/data/com.termux/files/usr/bin/chromium-browser"

package_install_and_check "chromium"