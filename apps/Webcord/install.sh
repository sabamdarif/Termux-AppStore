#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="webcord"
version="v4.10.5"
run_cmd="/opt/AppImageLauncher/webcord/usr/bin/webcord --no-sandbox"
app_type="distro"
supported_distro="all"
page_url="https://github.com/SpacingBat3/WebCord"

cd ${TMPDIR}

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="arm64" ;;
armv7*|arm) archtype="armv7l" ;;
esac

appimage_filename="WebCord-${version#v}-${archtype}.AppImage"

check_and_delete "${TMPDIR}/${appimage_filename} ${PREFIX}/share/applications/pd_added/webcord.desktop"

print_success "Downloading webcord AppImage..."
download_file "${page_url}/releases/download/${version}/${appimage_filename}"
install_appimage "$appimage_filename" "webcord"

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${PREFIX}/share/applications/pd_added/webcord.desktop >/dev/null
[Desktop Entry]
Name=Webcord
Exec=pdrun ${run_cmd}
Terminal=false
Type=Application
Icon=${HOME}/.appstore/logo/Webcord/logo.png
StartupWMClass=webcord
Comment=webcord
MimeType=x-scheme-handler/webcord;
Categories=Internet;
DESKTOP_EOF
