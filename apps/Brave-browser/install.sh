#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="brave-browser"
run_cmd="/opt/brave-browser/brave-browser --no-sandbox"
version="v1.90.122"
app_type="distro"
page_url="https://github.com/brave/brave-browser"
working_dir="${distro_path}/opt"
supported_distro="all"

progress_phase "prepare" 0 "Preparing..."

# Check if a distro is selected
if [ -z "$SELECTED_DISTRO" ]; then
	print_failed "Error: No distro selected"
	exit 1
fi

progress_phase "configure" 0 "Configuring..."
distro_run "
check_and_delete '/opt/brave-browser'
check_and_create_directory '/opt/brave-browser'
"
cd $working_dir/brave-browser
progress_phase "download" 0 "Downloading..."
download_file "${page_url}/releases/download/${version}/brave-browser-${version#v}-linux-arm64.zip"
progress_phase "extract" 0 "Extracting..."
distro_run "
cd /opt/brave-browser
extract brave-browser-${version#v}-linux-arm64.zip
check_and_delete brave-browser-${version#v}-linux-arm64.zip
"
progress_phase "desktop" 0 "Creating desktop entry..."
print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${TERMUX_PREFIX}/share/applications/pd_added/brave-browser.desktop >/dev/null
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

progress_done
