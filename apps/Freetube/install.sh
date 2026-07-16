#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="freetube"
version="v0.23.1-beta"
app_type="distro"
supported_distro="all"
page_url="https://github.com/FreeTubeApp/FreeTube"
run_cmd="/opt/AppImageLauncher/FreeTube/freetube --no-sandbox"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
declare -A sha256=(
	["freetube-0.23.1-arm64.AppImage"]="c6477b4db0d923996340af529e7900ff2008a3df397c9507c323840fc2b36be4"
	["freetube-0.23.1-armv7l.AppImage"]="c66c9939856c1a10bc7d92a1d2af669144be157a3cf20064fc3a18feb1171050"
)

cd "${TMPDIR}"

archtype=$(detect_arch aarch64=arm64 'armv7*=armv7l' arm=armv7l)
version_no_beta="$(echo "${version#v}" | sed 's/-.*$//')"
appimage_filename="freetube-${version_no_beta}-${archtype}.AppImage"

check_and_delete "${TMPDIR}/${appimage_filename} ${TERMUX_PREFIX}/share/applications/pd_added/freetube.desktop"

download_file "${page_url}/releases/download/${version}/${appimage_filename}"
install_appimage "$appimage_filename" "FreeTube"

create_desktop_entry \
	--name "FreeTube" --pkg "freetube" --logo-dir "Freetube" \
	--exec "${run_cmd}" \
	--wmclass "freetube" \
	--comment "YouTube app for privacy" \
	--categories "Internet;" \
	--mime "x-scheme-handler/;"
