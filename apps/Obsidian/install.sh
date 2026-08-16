#!/data/data/com.termux/files/usr/bin/bash

supported_arch="arm64"
version="v1.13.7"
app_type="distro"
supported_distro="all"
# working_dir="${distro_path}/opt/AppImageLauncher"
page_url="https://github.com/obsidianmd/obsidian-releases"
run_cmd="/opt/AppImageLauncher/Obsidian/obsidian --no-sandbox"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
sha256="e286fd2bb2a5d346a35a577bd764c73fd5537dddec2b99a1a3e5e35974085203"

cd ${TMPDIR}
appimage_filename="Obsidian-${version#v}-${supported_arch}.AppImage"

check_and_delete "${TMPDIR}/${appimage_filename} ${TERMUX_PREFIX}/share/applications/pd_added/obsidian.desktop"

download_file "${page_url}/releases/download/${version}/${appimage_filename}"
install_appimage "$appimage_filename" "Obsidian"

create_desktop_entry \
	--name "Obsidian" --pkg "obsidian" --logo-dir "Obsidian" \
	--exec "${run_cmd}" \
	--wmclass "obsidian" \
	--comment "Obsidian" \
	--categories "Office;" \
	--mime "x-scheme-handler/obsidian;"
