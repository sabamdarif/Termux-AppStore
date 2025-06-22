#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="void"
run_cmd="/opt/void/void --no-sandbox"
version="1.99.30040"
app_type="distro"
page_url="https://github.com/voideditor/binaries"
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

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="arm64" ;;
armv7* | arm | armv8l) archtype="armhf" ;;
*) print_failed "Unsupported architectures" ;;
esac

distro_run "
check_and_delete '/opt/void'
check_and_create_directory '/opt/void'
"
cd $working_dir/void
echo "$(pwd)"
download_file "${page_url}/releases/download/${version}/Void-linux-${archtype}-${version}.tar.gz"
distro_run "
cd /opt/void
echo '$(pwd)'
extract 'Void-linux-arm64-${version}.tar.gz'
check_and_delete 'Void-linux-arm64-${version}.tar.gz'
"

# Determine which logo file to use
if [ -f "${HOME}/.appstore/logo/Void/logo.png" ]; then
    icon_path="${HOME}/.appstore/logo/Void/logo.png"
elif [ -f "${HOME}/.appstore/logo/Void/logo.svg" ]; then
    icon_path="${HOME}/.appstore/logo/Void/logo.svg"
else
    icon_path="${HOME}/.appstore/logo/Void/logo"
fi

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${PREFIX}/share/applications/pd_added/void.desktop >/dev/null
[Desktop Entry]
Name=Void
Exec=pdrun "${run_cmd}"
Terminal=false
Type=Application
Icon=${icon_path}
StartupWMClass=void
Comment=Void an open source Cursor alternative.
MimeType=x-scheme-handler/void;
Categories=Development;
DESKTOP_EOF
