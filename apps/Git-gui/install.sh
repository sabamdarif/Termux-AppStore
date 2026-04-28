#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="git-gui"
run_cmd="/data/data/com.termux/files/usr/libexec/git-core/git-gui"
version="termux_local_version"
app_type="native"
progress_phase "prepare" 0 "Preparing to install git-gui..."
package_install_and_check "$package_name"
progress_done
