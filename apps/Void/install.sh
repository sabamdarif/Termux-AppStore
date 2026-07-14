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

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
declare -A sha256=(
	["Void-linux-arm64-1.99.30044.tar.gz"]="d2c818f1d73125e7afe3c6082c8f33116296bf6e73bd106830e0433840e70a4c"
	["Void-linux-armhf-1.99.30044.tar.gz"]="a7017b482e157d34ce3c2f712855da8fa0dff07ad531b80fc9061c2507820b7e"
)

if [ -z "$SELECTED_DISTRO" ]; then
	print_failed "Error: No distro selected"
fi

progress_phase "configure" 0 "Configuring..."
if [[ "$SELECTED_DISTRO" == "ubuntu" ]] || [[ "$SELECTED_DISTRO" == "debian" ]]; then
	distro_run "
sudo apt update -y -o Dpkg::Options::='--force-confnew'
sudo apt install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 libgbm1 libasound2 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libdrm2 libxcb-dri3-0 libxshmfence1
"
elif [[ "$SELECTED_DISTRO" == "fedora" ]]; then
	distro_run "
sudo dnf install -y nss atk at-spi2-atk gtk3 mesa-libgbm alsa-lib libX11-xcb libXcomposite libXdamage libXrandr libdrm libxcb libxshmfence libxkbcommon --skip-unavailable
"
else
	print_failed "Unsupported distro"
fi

archtype=$(detect_arch aarch64=arm64 'armv7*=armhf' arm=armhf armv8l=armhf)
filename="Void-linux-${archtype}-${version}.tar.gz"

install_archive_into_opt "void" "${page_url}/releases/download/${version}/${filename}"

create_desktop_entry \
	--name "Void" --pkg "void" --logo-dir "void" \
	--exec "${run_cmd}" \
	--wmclass "void" \
	--comment "Void an open source Cursor alternative." \
	--categories "Development;" \
	--mime "x-scheme-handler/void;"
