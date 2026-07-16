#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="webcord"
version="v4.13.2"
run_cmd="/opt/AppImageLauncher/webcord/usr/bin/webcord --no-sandbox"
app_type="distro"
supported_distro="all"
page_url="https://github.com/SpacingBat3/WebCord"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
declare -A sha256=(
	["WebCord-4.13.2-arm64.AppImage"]="c2992de5bb379efe1546d42a112ceb334cd5c10868cf7be1547b53aedd3ad493"
	["WebCord-4.13.2-armv7l.AppImage"]="587236a6ec6110303306f365fa2f659ab26d173727a73e10a69e24e99f40f261"
)

cd ${TMPDIR}

archtype=$(detect_arch aarch64=arm64 'armv7*=armv7l' arm=armv7l)
appimage_filename="WebCord-${version#v}-${archtype}.AppImage"

check_and_delete "${TMPDIR}/${appimage_filename} ${TERMUX_PREFIX}/share/applications/pd_added/webcord.desktop"

download_file "${page_url}/releases/download/${version}/${appimage_filename}"
install_appimage "$appimage_filename" "webcord"

create_desktop_entry \
	--name "Webcord" --pkg "webcord" --logo-dir "Webcord" \
	--exec "${run_cmd}" \
	--wmclass "webcord" \
	--comment "webcord" \
	--categories "Internet;" \
	--mime "x-scheme-handler/webcord;"
