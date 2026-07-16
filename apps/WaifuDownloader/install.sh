#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="waifudownloader"
run_cmd="waifudownloader"
version="0.2.69"
app_type="native"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
sha256="ce5c4d8942697b762d18765b6dca5e817fe7a3845be800a5c83828c563661e63"

archtype=$(detect_arch aarch64=aarch64)
deb_file_name="waifudownloader_${version}_${archtype}.deb"
install_deb_into_termux "https://github.com/WOOD6563/WaifuDownloader-termux/releases/download/Master/${deb_file_name}"
