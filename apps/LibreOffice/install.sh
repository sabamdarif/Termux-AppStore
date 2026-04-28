#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
version=distro_local_version
app_type="distro"
supported_distro="all"
# working_dir=""
package_name="libreoffice"
run_cmd="libreoffice"

progress_phase "prepare" 0 "Preparing..."
progress_phase "install" 0 "Installing..."

case "$SELECTED_DISTRO" in
"debian" | "ubuntu")
	pd_package_install_and_check "libreoffice libreoffice-gtk3"
	;;
"fedora")
	pd_package_install_and_check libreoffice
	;;
"arch*")
	pd_package_install_and_check libreoffice-fresh
	;;
*)
	echo "Unsupported distribution: $SELECTED_DISTRO"
	exit 1
	;;
esac
progress_done