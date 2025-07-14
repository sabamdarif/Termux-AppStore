#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="dconf-editor"
run_cmd="dconf-editor"
version="45.0.1"
app_type="native"

cd ${TMPDIR}

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="aarch64" ;;
armv7* | arm | armv8l*) archtype="arm" ;;
*) print_failed "Unsupported architectures" ;;
esac

deb_file_name="dconf-editor_${version}_${archtype}.deb"
check_and_delete "$deb_file_name"
download_file "https://github.com/sabamdarif/Termux-AppStore/releases/download/files/${deb_file_name}"
dpkg --configure -a
apt --fix-broken install -y
apt install ./${deb_file_name} -y
