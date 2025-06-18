#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="linuxthemestore-git"
run_cmd="linuxthemestore"
version="v1.0.4"
app_type="native"

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="arm64" ;;
armv7* | arm) archtype="arm" ;;
*) print_failed "Unsupported architectures" ;;
esac

deb_file_name="linuxthemestore-git_${version}_${archtype}.deb"
download_file "https://github.com/sabamdarif/linuxthemestore/releases/download/${version}-termux/${deb_file_name}"
dpkg --configure -a
apt --fix-broken install -y
apt install ./${deb_file_name} -y
