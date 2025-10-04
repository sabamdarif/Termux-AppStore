#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="blender"
run_cmd="blender-4.5"
version="4.5.3"
app_type="native"

cd "${TMPDIR}" || exit 1

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="aarch64" ;;
*) print_failed "Unsupported architectures" ;;
esac

deb_file_name="blender4_${version}_${archtype}.zip"
mkdir blender
cd blender || exit 1
check_and_delete "$deb_file_name"
download_file "https://github.com/sabamdarif/Termux-AppStore/releases/download/files/${deb_file_name}"
dpkg --configure -a
apt --fix-broken install -y
apt install ./*.deb -y
