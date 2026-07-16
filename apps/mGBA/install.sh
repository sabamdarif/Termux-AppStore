#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm64"
version="0.10.5"
app_type="distro"
supported_distro="all"
page_url="https://github.com/mgba-emu/mgba"
run_cmd="/usr/local/bin/mgba-appimage"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
sha256="de3cbf437be1d5324c3853baba0dafea3311322a23829355d583308947e058e8"

if [ -z "$SELECTED_DISTRO" ]; then
	print_failed "Error: No distro selected"
fi

cd "${TMPDIR}" || exit 1
appimage_filename="mGBA-${version#v}-appimage-arm64.appimage"

check_and_delete "${TMPDIR}/${appimage_filename}"
check_and_delete "${TERMUX_PREFIX}/share/applications/pd_added/mgba.desktop"

download_file "${page_url}/releases/download/${version}/${appimage_filename}"
install_appimage "$appimage_filename" "mGBA"

wrapper_setup_content=$(
	cat <<'WRAPPER_SETUP'
set -e
cat >/usr/local/bin/mgba-appimage <<'WRAPPER_EOF'
#!/bin/sh
export APPDIR=/opt/AppImageLauncher/mGBA
cd /opt/AppImageLauncher/mGBA || exit 1
exec ./AppRun "$@"
WRAPPER_EOF
chmod +x /usr/local/bin/mgba-appimage
WRAPPER_SETUP
)
distro_run "$wrapper_setup_content"

create_desktop_entry \
	--name "mGBA" --pkg "mgba" --logo-dir "mGBA" \
	--exec "${run_cmd}" \
	--wmclass "mgba-qt" \
	--comment "Game Boy Advance emulator" \
	--categories "Game;Emulator;"
