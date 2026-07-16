#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="youtube-music"
run_cmd="youtube-music"
version="v3.11.0"
app_type="distro"
supported_distro="all"
page_url="https://github.com/th-ch/youtube-music"
run_cmd="/opt/AppImageLauncher/youtube-music/youtube-music --no-sandbox"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
sha256="834962b462cbefe5bdff0b16fb684875503879ed37a54ff1f6d84164fe6b1dd6"

archtype=$(detect_arch aarch64=arm64)

cd ${TMPDIR}

appimage_filename="YouTube-Music-${version#v}-${archtype}.AppImage"

check_and_delete "${TMPDIR}/${appimage_filename} ${TERMUX_PREFIX}/share/applications/pd_added/youtube-music.desktop"

download_file "${page_url}/releases/download/${version}/$appimage_filename"
install_appimage "$appimage_filename" "youtube-music"

create_desktop_entry \
	--name "Youtube-music" --pkg "youtube-music" --logo-dir "Youtube-music" \
	--exec "${run_cmd}" \
	--wmclass "youtube-music" \
	--comment "youtube-music" \
	--categories "Multimedia;" \
	--mime "x-scheme-handler/youtube-music;"
