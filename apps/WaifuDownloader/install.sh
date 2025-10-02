#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="waifudownloader"
version="0.2.9"
app_type="native"

deb_file_name="${package_name}_${version}_${supported_arch}.deb"
download_url="https://github.com/WOOD6563/WaifuDownloader-termux/releases/download/Master/${deb_file_name}"

dpkg --configure -a
apt --fix-broken install -y
apt install ./"$deb_file_name" -y
