#!/data/data/com.termux/files/usr/bin/bash

supported_arch="arm64"
version="v1.11.7"
app_type="distro"
supported_distro="all"
# working_dir="${distro_path}/opt/AppImageLauncher"
page_url="https://github.com/obsidianmd/obsidian-releases"
run_cmd="/opt/AppImageLauncher/Obsidian/obsidian --no-sandbox"

cd ${TMPDIR}
# Get the correct filename that will be downloaded
appimage_filename="Obsidian-${version#v}-${supported_arch}.AppImage"

check_and_delete "${TMPDIR}/${appimage_filename} ${PREFIX}/share/applications/obsidian.desktop"

print_success "Downloading Obsidian AppImage..."
download_file "${page_url}/releases/download/${version}/Obsidian-${version#v}-${supported_arch}.AppImage"
install_appimage "$appimage_filename" "Obsidian"

print_success "Creating desktop entry..."
cat <<EOF | tee ${PREFIX}/share/applications/pd_added/obsidian.desktop >/dev/null
[Desktop Entry]
Name=Obsidian
Exec=pdrun ${run_cmd}
Terminal=false
Type=Application
Icon=${HOME}/.appstore/logo/Obsidian/logo.png
StartupWMClass=obsidian
Comment=Obsidian
MimeType=x-scheme-handler/obsidian;
Categories=Office;
EOF