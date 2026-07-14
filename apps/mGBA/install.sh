#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm64"
version="0.10.5"
app_type="distro"
supported_distro="all"
page_url="https://github.com/mgba-emu/mgba"
run_cmd="/usr/local/bin/mgba-appimage"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
sha256="de3cbf437be1d5324c3853baba0dafea3311322a23829355d583308947e058e8"

progress_phase "prepare" 0 "Preparing mGBA..."

if [ -z "$SELECTED_DISTRO" ]; then
	print_failed "Error: No distro selected"
	exit 1
fi

cd "${TMPDIR}" || exit 1
appimage_filename="mGBA-${version#v}-appimage-arm64.appimage"

check_and_delete "${TMPDIR}/${appimage_filename}"
check_and_delete "${TERMUX_PREFIX}/share/applications/pd_added/mgba.desktop"

progress_phase "download" 0 "Downloading mGBA ARM64 AppImage..."
download_file "${page_url}/releases/download/${version}/${appimage_filename}"

progress_phase "configure" 0 "Installing mGBA AppImage..."
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

progress_phase "desktop" 0 "Creating desktop entry..."
check_and_create_directory "${TERMUX_PREFIX}/share/applications/pd_added"
cat >"${TERMUX_PREFIX}/share/applications/pd_added/mgba.desktop" <<EOF
[Desktop Entry]
Name=mGBA
Exec=pdrun ${run_cmd}
Terminal=false
Type=Application
Icon=${HOME}/.appstore/logo/mGBA/logo.png
StartupWMClass=mgba-qt
Comment=Game Boy Advance emulator
Categories=Game;Emulator;
EOF

progress_done
