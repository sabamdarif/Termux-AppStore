#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="freetube"
version="v0.23.1-beta"
app_type="distro"
supported_distro="all"
page_url="https://github.com/FreeTubeApp/FreeTube"
run_cmd="/opt/AppImageLauncher/FreeTube/freetube --no-sandbox"

progress_phase "prepare" 0 "Preparing..."
cd "${TMPDIR}"

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="arm64" ;;
armv7*|arm) archtype="armv7l" ;;
esac

version_no_beta="$(echo "${version#v}" | sed 's/-.*$//')"
appimage_filename="freetube-${version_no_beta}-${archtype}.AppImage"

check_and_delete "${TMPDIR}/${appimage_filename} ${TERMUX_PREFIX}/share/applications/pd_added/freetube.desktop"

print_success "Downloading FreeTube AppImage..."
progress_phase "download" 0 "Downloading..."
download_file "${page_url}/releases/download/${version}/${appimage_filename}"
progress_phase "configure" 0 "Configuring..."
install_appimage "$appimage_filename" "FreeTube"

progress_phase "desktop" 0 "Creating desktop entry..."
print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee "${TERMUX_PREFIX}/share/applications/pd_added/freetube.desktop" >/dev/null
[Desktop Entry]
Name=FreeTube
Exec=pdrun ${run_cmd}
Terminal=false
Type=Application
Icon=${HOME}/.appstore/logo/Freetube/logo.png
StartupWMClass=freetube
Comment=YouTube app for privacy
MimeType=x-scheme-handler/;
Categories=Internet;
DESKTOP_EOF

progress_done