#!/data/data/com.termux/files/usr/bin/bash

supported_arch="arm64"
version="v1.12.7"
app_type="distro"
supported_distro="all"
# working_dir="${distro_path}/opt/AppImageLauncher"
page_url="https://github.com/obsidianmd/obsidian-releases"
run_cmd="/opt/AppImageLauncher/Obsidian/obsidian --no-sandbox"

progress_phase "prepare" 0 "Preparing..."
cd ${TMPDIR}
# Get the correct filename that will be downloaded
appimage_filename="Obsidian-${version#v}-${supported_arch}.AppImage"

check_and_delete "${TMPDIR}/${appimage_filename} ${TERMUX_PREFIX}/share/applications/obsidian.desktop"

print_success "Downloading Obsidian AppImage..."
progress_phase "download" 0 "Downloading..."
download_file "${page_url}/releases/download/${version}/Obsidian-${version#v}-${supported_arch}.AppImage"
progress_phase "configure" 0 "Configuring..."
install_appimage "$appimage_filename" "Obsidian"

progress_phase "desktop" 0 "Creating desktop entry..."
print_success "Creating desktop entry..."
cat <<EOF | tee ${TERMUX_PREFIX}/share/applications/pd_added/obsidian.desktop >/dev/null
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

progress_done