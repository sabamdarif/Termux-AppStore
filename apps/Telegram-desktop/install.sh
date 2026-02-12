#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="telegram-desktop"
run_cmd="telegram-desktop"
version="termux_local_version"
app_type="native"
package_remove_and_check "libobjc2"
package_install_and_check "$package_name protobuf"
