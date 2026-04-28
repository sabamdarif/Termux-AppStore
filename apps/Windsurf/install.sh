#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="windsurf"
run_cmd="/opt/windsurf/windsurf --no-sandbox"
version="v1.3.4"
app_type="distro"
page_url="https://github.com/rodriguezst/windsurf-arm"
working_dir="${distro_path}/opt"
supported_distro="all"

progress_phase "prepare" 0 "Preparing..."

# Check if a distro is selected
if [ -z "$SELECTED_DISTRO" ]; then
    print_failed "Error: No distro selected"
    exit 1
fi

if [[ "$SELECTED_DISTRO" == "debian" ]] || [[ "$SELECTED_DISTRO" == "ubuntu" ]]; then
	progress_phase "configure" 0 "Configuring..."
	distro_run "
sudo apt update -y -o Dpkg::Options::="--force-confnew" && sudo apt install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 libgbm1 libasound2 libx11-xcb1  libxcomposite1  libxdamage1 libxrandr2  libdrm2 libxcb-dri3-0 libxshmfence1
"
elif [[ "$SELECTED_DISTRO" == "fedora" ]]; then
	progress_phase "configure" 0 "Configuring..."
	distro_run "
sudo dnf install -y nss atk at-spi2-atk gtk3 mesa-libgbm alsa-lib libX11-xcb libXcomposite libXdamage libXrandr libdrm  libxcb libxshmfence libxkbcommon --skip-unavailable
"
fi

progress_phase "configure" 0 "Configuring..."
distro_run "
check_and_delete '/opt/windsurf'
check_and_create_directory '/opt/windsurf'
"
cd $working_dir/windsurf
echo "$(pwd)"
progress_phase "download" 0 "Downloading..."
download_file "${page_url}/releases/download/${version}/windsurf_${version#v}_linux_arm64.tar.gz"
progress_phase "extract" 0 "Extracting..."
distro_run "
cd /opt/windsurf
echo '$(pwd)'
extract 'windsurf_${version#v}_linux_arm64.tar.gz'
check_and_delete 'windsurf_${version#v}_linux_arm64.tar.gz'
"

# Determine which logo file to use
if [ -f "${HOME}/.appstore/logo/Windsurf/logo.png" ]; then
    icon_path="${HOME}/.appstore/logo/Windsurf/logo.png"
elif [ -f "${HOME}/.appstore/logo/Windsurf/logo.svg" ]; then
    icon_path="${HOME}/.appstore/logo/Windsurf/logo.svg"
else
    icon_path="${HOME}/.appstore/logo/Windsurf/logo"
fi

progress_phase "desktop" 0 "Creating desktop entry..."
print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${TERMUX_PREFIX}/share/applications/pd_added/windsurf.desktop >/dev/null
[Desktop Entry]
Name=Windsurf
Exec=pdrun "${run_cmd}"
Terminal=false
Type=Application
Icon=${icon_path}
StartupWMClass=windsurf
Comment=windsurf
MimeType=x-scheme-handler/windsurf;
Categories=Development;
DESKTOP_EOF

progress_done
