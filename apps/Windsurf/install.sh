#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="windsurf"
run_cmd="/opt/windsurf/windsurf --no-sandbox"
version="v1.3.4"
app_type="distro"
page_url="https://github.com/rodriguezst/windsurf-arm"
working_dir="${distro_path}/opt"
supported_distro="all"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
sha256="d945a6bb53e0dfcacd3cb0593f24f09c55a3f3585c401b0f86127f77eac83c6a"

if [ -z "$SELECTED_DISTRO" ]; then
	print_failed "Error: No distro selected"
fi

progress_phase "configure" 0 "Configuring..."
if [[ "$SELECTED_DISTRO" == "debian" ]] || [[ "$SELECTED_DISTRO" == "ubuntu" ]]; then
	distro_run "
sudo apt update -y -o Dpkg::Options::='--force-confnew'
sudo apt install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 libgbm1 libasound2 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libdrm2 libxcb-dri3-0 libxshmfence1
"
elif [[ "$SELECTED_DISTRO" == "fedora" ]]; then
	distro_run "
sudo dnf install -y nss atk at-spi2-atk gtk3 mesa-libgbm alsa-lib libX11-xcb libXcomposite libXdamage libXrandr libdrm libxcb libxshmfence libxkbcommon --skip-unavailable
"
fi

install_archive_into_opt "windsurf" "${page_url}/releases/download/${version}/windsurf_${version#v}_linux_arm64.tar.gz"

create_desktop_entry \
	--name "Windsurf" --pkg "windsurf" --logo-dir "Windsurf" \
	--exec "${run_cmd}" \
	--wmclass "windsurf" \
	--comment "windsurf" \
	--categories "Development;" \
	--mime "x-scheme-handler/windsurf;"
