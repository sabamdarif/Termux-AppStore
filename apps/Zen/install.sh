#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="zen-browser"
run_cmd="/opt/zen-browser/zen-browser --no-sandbox"
version="1.16.3b"
app_type="distro"
page_url="https://github.com/zen-browser/desktop"
working_dir="${distro_path}/opt"
supported_distro="all"

# Check if a distro is selected
if [ -z "$selected_distro" ]; then
    print_failed "Error: No distro selected"
    exit 1
fi

distro_run "
check_and_delete '/opt/zen-browser'
"
cd $working_dir
echo "$(pwd)"

download_file "${page_url}/releases/download/${version}/zen.linux-${supported_arch}.tar.xz"
distro_run '
cd /opt
extract "zen.linux-'${supported_arch}'.tar.xz"
check_and_delete "zen.linux-'${supported_arch}'.tar.xz"
mv -f zen zen-browser
sleep 3
check_and_create_directory "/opt/zen-browser/"
cd /opt/zen-browser/
echo "$(pwd)"
ls
mv zen zen-browser
'

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${PREFIX}/share/applications/pd_added/zen-browser.desktop >/dev/null
[Desktop Entry]
Name=Zen Browser
Comment=Experience tranquillity while browsing the web without people tracking you!
Exec=pdrun ${run_cmd}
Icon=${HOME}/.appstore/logo/Zen/logo.png
Type=Application
MimeType=text/html;text/xml;application/xhtml+xml;x-scheme-handler/http;x-scheme-handler/https;application/x-xpinstall;application/pdf;application/json;
StartupWMClass=zen-beta
Categories=Network;WebBrowser;
StartupNotify=true
Terminal=false
DESKTOP_EOF
