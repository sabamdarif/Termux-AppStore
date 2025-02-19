#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="freetube"
version=v0.23.1-beta
app_type="distro"
supported_distro="all"
page_url="https://github.com/FreeTubeApp/FreeTube"
run_cmd="/opt/AppImageLauncher/FreeTube/freetube --no-sandbox"

cd ${TMPDIR}

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="arm64" ;;
armv7*|arm) archtype="armv7l" ;;
esac

appimage_filename="freetube-${version#v}-${archtype}.AppImage"

check_and_delete "${TMPDIR}/${appimage_filename} ${PREFIX}/share/applications/pd_added/freetube.desktop"

print_success "Downloading FreeTube AppImage..."
download_file "${page_url}/releases/download/${version}/${appimage_filename}"
install_appimage "$appimage_filename" "FreeTube"

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${PREFIX}/share/applications/pd_added/freetube.desktop >/dev/null
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
