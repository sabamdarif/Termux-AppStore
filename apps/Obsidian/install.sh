#!/data/data/com.termux/files/usr/bin/bash

supported_arch="arm64"
version=v1.8.4
app_type="distro"
supported_distro="all"
# working_dir="${distro_path}/opt/AppImageLauncher"
page_url="https://github.com/obsidianmd/obsidian-releases"
run_cmd="/opt/AppImageLauncher/Obsidian/obsidian --no-sandbox"

cd ${TMPDIR}

print_success "Downloading Obsidian AppImage..."
download_file "${page_url}/download/v${version}/Obsidian-${version}-${supported_arch}.AppImage"
install_appimage "Obsidian-${version}-${supported_arch}.AppImage" "Obsidian"

print_success "Downloading and installing icons..."
download_file "https://raw.githubusercontent.com/Pi-Apps-Coders/files/main/obsidian-hicolor.tar.gz"
tar -xf obsidian-hicolor.tar.gz -C ${distro_path}/usr/share/icons
check_and_delete "obsidian-hicolor.tar.gz"

print_success "Creating desktop entry..."
cat <<EOF | tee ${PREFIX}/share/applications/obsidian.desktop >/dev/null
[Desktop Entry]
Name=Obsidian
Exec=pdrun ${run_cmd}
Terminal=false
Type=Application
Icon=obsidian
StartupWMClass=obsidian
Comment=Obsidian
MimeType=x-scheme-handler/obsidian;
Categories=Office;
EOF