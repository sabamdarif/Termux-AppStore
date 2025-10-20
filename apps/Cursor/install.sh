#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="cursor"
version="1.7.52"
app_type="distro"
supported_distro="all"
page_url="https://downloads.cursor.com/production/9675251a06b1314d50ff34b0cbe5109b78f848cd/linux/arm64"
pause_update=true
run_cmd="/opt/AppImageLauncher/cursor/AppRun --no-sandbox"

cd "${TMPDIR}" || exit 1

appimage_filename="Cursor-${version}-${supported_arch}.AppImage"

check_and_delete "${TMPDIR}/${appimage_filename} ${PREFIX}/share/applications/pd_added/cursor.desktop"

print_success "Downloading cursor AppImage..."
download_file "${page_url}/$appimage_filename"
install_appimage "$appimage_filename" "cursor"

# Determine which logo file to use
if [ -f "${HOME}/.appstore/logo/Cursor/logo.png" ]; then
    icon_path="${HOME}/.appstore/logo/Cursor/logo.png"
elif [ -f "${HOME}/.appstore/logo/Cursor/logo.svg" ]; then
    icon_path="${HOME}/.appstore/logo/Cursor/logo.svg"
else
    icon_path="${HOME}/.appstore/logo/Cursor/logo"
fi

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${PREFIX}/share/applications/pd_added/cursor.desktop >/dev/null
[Desktop Entry]
Name=Cursor
Exec=pdrun "${run_cmd}"
Terminal=false
Type=Application
Icon=${icon_path}
StartupWMClass=cursor
Comment=cursor
MimeType=x-scheme-handler/cursor;
Categories=Development;
DESKTOP_EOF
