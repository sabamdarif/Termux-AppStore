#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="windsurf"
run_cmd="/opt/windsurf/windsurf --no-sandbox"
version="v1.3.4"
app_type="distro"
page_url="https://github.com/rodriguezst/windsurf-arm"
working_dir="${distro_path}/opt"
supported_distro="all"

# Check if a distro is selected
if [ -z "$selected_distro" ]; then
    print_failed "Error: No distro selected"
    exit 1
fi

if [[ "$selected_distro" == "debian" ]] || [[ "$selected_distro" == "ubuntu" ]]; then
distro_run "
sudo apt update -y -o Dpkg::Options::="--force-confnew" && sudo apt install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 libgbm1 libasound2 libx11-xcb1  libxcomposite1  libxdamage1 libxrandr2  libdrm2 libxcb-dri3-0 libxshmfence1
"
elif [[ "$selected_distro" == "fedora" ]]; then
distro_run "
sudo dnf install -y nss atk at-spi2-atk gtk3 mesa-libgbm alsa-lib libX11-xcb libXcomposite libXdamage libXrandr libdrm  libxcb libxshmfence libxkbcommon --skip-unavailable
"
fi

distro_run "
check_and_delete '/opt/windsurf'
check_and_create_directory '/opt/windsurf'
"
cd $working_dir/windsurf
echo "$(pwd)"
download_file "${page_url}/releases/download/${version}/windsurf_${version#v}_linux_arm64.tar.gz"
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

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${PREFIX}/share/applications/pd_added/windsurf.desktop >/dev/null
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
