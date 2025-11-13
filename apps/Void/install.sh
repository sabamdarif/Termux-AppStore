#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="void"
run_cmd="/opt/void/void --no-sandbox"
version="1.99.30044"
pause_update=true
app_type="distro"
supported_distro="all"
page_url="https://github.com/voideditor/binaries"
working_dir="${distro_path}/opt"

if [[ "$selected_distro" == "ubuntu" ]] || [[ "$selected_distro" == "debian" ]]; then
	distro_run "
sudo apt update -y -o Dpkg::Options::='--force-confnew'
sudo apt install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 libgbm1 libasound2 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libdrm2 libxcb-dri3-0 libxshmfence1
"
elif [[ "$selected_distro" == "fedora" ]]; then
	distro_run "
sudo dnf install -y nss atk at-spi2-atk gtk3 mesa-libgbm alsa-lib libX11-xcb libXcomposite libXdamage libXrandr libdrm libxcb libxshmfence libxkbcommon --skip-unavailable
"
else
	print_failed "Unsupported distro"
fi

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="arm64" ;;
armv7* | arm | armv8l) archtype="armhf" ;;
*) print_failed "Unsupported architectures" ;;
esac

filename="Void-linux-${archtype}-${version}.tar.gz"
temp_download="$TMPDIR/${filename}"
download_file "$temp_download" "${page_url}/releases/download/${version}/${filename}"

distro_run "
check_and_delete '/opt/void'
check_and_create_directory '/opt/void'
"

if [[ "$selected_distro_type" == "chroot" ]]; then
	su -c "cp '$temp_download' '${working_dir}/void/${filename}'"
else
	cp "$temp_download" "${working_dir}/void/${filename}"
fi

distro_run "
cd /opt/void
extract '${filename}'
check_and_delete '${filename}'
"

# Determine which logo file to use
if [ -f "${HOME}/.appstore/logo/void/logo.png" ]; then
	icon_path="${HOME}/.appstore/logo/void/logo.png"
elif [ -f "${HOME}/.appstore/logo/void/logo.svg" ]; then
	icon_path="${HOME}/.appstore/logo/void/logo.svg"
else
	icon_path="${HOME}/.appstore/logo/void/logo"
fi

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee "${PREFIX}"/share/applications/pd_added/void.desktop >/dev/null
[Desktop Entry]
Name=Void
Exec=pdrun ${run_cmd}
Terminal=false
Type=Application
Icon=${icon_path}
StartupWMClass=void
Comment=Void an open source Cursor alternative.
MimeType=x-scheme-handler/void;
Categories=Development;
DESKTOP_EOF
