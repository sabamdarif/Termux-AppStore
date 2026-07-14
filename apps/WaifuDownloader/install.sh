#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="waifudownloader"
run_cmd="waifudownloader"
version="0.2.69"
app_type="native"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
sha256="ce5c4d8942697b762d18765b6dca5e817fe7a3845be800a5c83828c563661e63"

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="aarch64" ;;
*) print_failed "Unsupported architectures" ;;
esac

deb_file_name="waifudownloader_${version}_${archtype}.deb"
check_and_delete "$deb_file_name"
download_file "https://github.com/WOOD6563/WaifuDownloader-termux/releases/download/Master/${deb_file_name}"
dpkg --configure -a
apt --fix-broken install -y
apt install ./${deb_file_name} -y
