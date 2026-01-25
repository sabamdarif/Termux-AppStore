#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="brave-browser"
run_cmd="/opt/brave-browser/brave-browser --no-sandbox"
version="v1.86.142"
app_type="distro"
page_url="https://github.com/brave/brave-browser"
working_dir="${distro_path}/opt"
supported_distro="all"

# Check if a distro is selected
if [ -z "$selected_distro" ]; then
    print_failed "Error: No distro selected"
    exit 1
fi

distro_run "
check_and_delete '/opt/brave-browser'
check_and_create_directory '/opt/brave-browser'
"
cd $working_dir/brave-browser
echo "$(pwd)"
download_file "${page_url}/releases/download/${version}/brave-browser-${version#v}-linux-arm64.zip"
distro_run "
cd /opt/brave-browser
echo $(pwd)
extract brave-browser-${version#v}-linux-arm64.zip
check_and_delete brave-browser-${version#v}-linux-arm64.zip
"
print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${PREFIX}/share/applications/pd_added/brave-browser.desktop >/dev/null
[Desktop Entry]
Name=Brave-browser
Exec=pdrun ${run_cmd}
Terminal=false
Type=Application
Icon=${HOME}/.appstore/logo/Brave-browser/logo.png
StartupWMClass=brave-browser
Comment=Brave is a free and open-source web browser
MimeType=x-scheme-handler/brave-browser;
Categories=Internet;
DESKTOP_EOF
