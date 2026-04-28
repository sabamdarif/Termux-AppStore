#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="blender4"
run_cmd="blender-4.5"
version="termux_local_version"
app_type="native"
progress_phase "prepare" 0 "Preparing to install blender4..."
package_install_and_check "$package_name"
progress_done
