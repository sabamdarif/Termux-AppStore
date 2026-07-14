#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="linuxthemestore-git"
run_cmd="linuxthemestore"
version="v1.0.4"
app_type="native"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
declare -A sha256=(
	["linuxthemestore-git_1.0.4_aarch64.deb"]="73325cc98731315793fc88fe96496f0e7332aa3603a68e2a5abd6b2a4935fb93"
	["linuxthemestore-git_1.0.4_arm.deb"]="d70848781f51fe0e59ee1075048b1f7f86a86a7daac899bbfe90633e68ffa4e0"
)

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="aarch64" ;;
armv7* | arm) archtype="arm" ;;
*) print_failed "Unsupported architectures" ;;
esac

deb_file_name="linuxthemestore-git_${version#v}_${archtype}.deb"
progress_phase "prepare" 0 "Preparing to install linuxthemestore-git..."
download_file "https://github.com/sabamdarif/linuxthemestore/releases/download/${version#v}-termux/${deb_file_name}"
dpkg --configure -a
apt --fix-broken install -y
apt install ./${deb_file_name} -y
progress_done
