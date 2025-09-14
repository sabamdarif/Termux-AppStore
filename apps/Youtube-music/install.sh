#!/data/data/com.termux/files/usr/bin/bash

supported_arch="Invalid,choice(s).,Please,choose,from:,aarch64,arm,aarch64,arm"
package_name="youtube-music"
run_cmd="youtube-music"
version="v3.11.0"
app_type="distro"
supported_distro="all"
page_url="https://github.com/th-ch/youtube-music"
run_cmd="/opt/AppImageLauncher/youtube-music/youtube-music --no-sandbox"

cd ${TMPDIR}

app_arch=$(uname -m)
case " $app_arch" in
aarch64) archtype="arm64" ;;
armv7*|arm) archtype="armv7l" ;;
esac

appimage_filename="YouTube-Music-${version#v}-arm64.AppImage"

check_and_delete "${TMPDIR}/${appimage_filename} ${PREFIX}/share/applications/pd_added/youtube-music.desktop"

print_success "Downloading youtube-music AppImage..."
download_file "${page_url}/releases/download/${version}/$appimage_filename"
install_appimage "$appimage_filename" "youtube-music"

# Determine which logo file to use
if [ -f "${HOME}/.appstore/logo/Youtube-music/logo.png" ]; then
    icon_path="${HOME}/.appstore/logo/Youtube-music/logo.png"
elif [ -f "${HOME}/.appstore/logo/Youtube-music/logo.svg" ]; then
    icon_path="${HOME}/.appstore/logo/Youtube-music/logo.svg"
else
    icon_path="${HOME}/.appstore/logo/Youtube-music/logo"
fi

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${PREFIX}/share/applications/pd_added/youtube-music.desktop >/dev/null
[Desktop Entry]
Name=Youtube-music
Exec=pdrun "${run_cmd}"
Terminal=false
Type=Application
Icon=${icon_path}
StartupWMClass=youtube-music
Comment=youtube-music
MimeType=x-scheme-handler/youtube-music;
Categories=Multimedia;
DESKTOP_EOF
