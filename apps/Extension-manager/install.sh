#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="extension-manager"
run_cmd="extension-manager"
version="0.6.3"
app_type="native"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
declare -A sha256=(
	["extension-manager_0.6.3_aarch64.deb"]="7ee6ab5a21c4919d85239e3e6c64745be53144f390aaf2c5cf55b9e39c82c36d"
	["extension-manager_0.6.3_arm.deb"]="3f6fc12a20c3b00bd2ae787a122b6ba66774079e55baf1b3f0ca46d7d9bd755f"
)

cd ${TMPDIR}

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="aarch64" ;;
armv7* | arm | armv8l*) archtype="arm" ;;
*) print_failed "Unsupported architectures" ;;
esac

deb_file_name="extension-manager_${version}_${archtype}.deb"
check_and_delete "$deb_file_name"
download_file "https://github.com/sabamdarif/Termux-AppStore/releases/download/files/${deb_file_name}"
dpkg --configure -a
apt --fix-broken install -y
apt install ./${deb_file_name} -y
