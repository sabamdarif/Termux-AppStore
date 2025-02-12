#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="cursor"
run_cmd="/opt/cursor/cursor --no-sandbox"
version=v0.44.0
app_type="distro"
page_url="https://github.com/coder/cursor-arm"
working_dir="${distro_path}/opt"
supported_distro="all"

# Check if a distro is selected
if [ -z "$selected_distro" ]; then
    print_failed "Error: No distro selected"
    exit 1
fi

app_arch=$(uname -m)

case "$app_arch" in
aarch64) supported_arch="arm64" ;;
armv7*|arm) supported_arch="arm32" ;;
esac

distro_run "check_and_delete /opt/cursor"
distro_run "check_and_create_directory /opt/cursor"
cd ${working_dir}/cursor
echo "$(pwd)"
download_file "${page_url}/releases/download/${version}/cursor_${version#v}_linux_${supported_arch}.tar.gz"

distro_run '
cd /opt/cursor
echo "$(pwd)"
extract "cursor_'${version#v}'_linux_'${supported_arch}'.tar.gz"
check_and_delete "cursor_'${version#v}'_linux_'${supported_arch}'.tar.gz"
'
print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${PREFIX}/share/applications/pd_added/cursor.desktop >/dev/null
[Desktop Entry]
Name=Cursor
Exec=pdrun ${run_cmd}
Terminal=false
Type=Application
Icon=${HOME}/.appstore/logo/Cursor/logo.png
StartupWMClass=cursor
Comment=Cursor is an AI-first coding environment.
MimeType=x-scheme-handler/cursor;
Categories=Development;
DESKTOP_EOF
