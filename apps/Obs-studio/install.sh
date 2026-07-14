#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="obs-studio"
run_cmd="obs"
version="32.1.2"
_libdatachannel_version="0.24.2"
_qrcodegen_version="1.8.0"
_websocketpp_version="0.8.2"
app_type="native"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
declare -A sha256=(
	["libdatachannel_0.24.2_aarch64.deb"]="ed14a03991ba54c5988645eab3317150f0057f38971518e0139e332febb38e27"
	["obs-studio_32.1.2_aarch64.deb"]="c510b2808b1768c5e90146cbe1efb1a00acd8500afbbeb25301448f9dfd40b15"
	["qrcodegen_1.8.0_aarch64.deb"]="597b17ed21902cead3a065ad5a5e80fc9eba27f4d64b07e5c50677aa67152e60"
	["websocketpp_0.8.2_aarch64.deb"]="ad63ecd19d2f5e786f64bdc506fa534725c8d89a9d4367e631092b610812e63a"
)

detact_package_manager

if [[ "$PACKAGE_MANAGER" == "pacman" ]]; then
	print_failed "pacman isn't supported"
	progress_error "pacman isn't supported"
	exit 1
fi

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="aarch64" ;;
armv7* | arm) archtype="armv7l" ;;
*)
	print_failed "Unsupported architecture: $app_arch"
	progress_error "Unsupported architecture"
	exit 1
	;;
esac

progress_phase "prepare" 0 "Preparing to install OBS Studio..."

cd "$TMPDIR" || {
	print_failed "tmp dir not found"
	progress_error "tmp dir not found"
	exit 1
}

check_and_create_directory "obs-studio-dl"
cd obs-studio-dl || {
	print_failed "Failed to enter obs-studio-dl directory"
	progress_error "Failed to enter directory"
	exit 1
}

check_and_delete "obs-studio_${version}_${archtype}.deb" \
	"libdatachannel_${_libdatachannel_version}_${archtype}.deb" \
	"qrcodegen_${_qrcodegen_version}_${archtype}.deb" \
	"websocketpp_${_websocketpp_version}_${archtype}.deb"

progress_phase "download" 10 "Downloading OBS Studio packages..."

download_file "https://github.com/sabamdarif/Termux-AppStore/releases/download/files/obs-studio_${version}_${archtype}.deb" || {
	print_failed "Failed to download obs-studio"
	progress_error "Download failed"
	exit 1
}

download_file "https://github.com/sabamdarif/Termux-AppStore/releases/download/files/libdatachannel_${_libdatachannel_version}_${archtype}.deb" || {
	print_failed "Failed to download libdatachannel"
	progress_error "Download failed"
	exit 1
}

download_file "https://github.com/sabamdarif/Termux-AppStore/releases/download/files/qrcodegen_${_qrcodegen_version}_${archtype}.deb" || {
	print_failed "Failed to download qrcodegen"
	progress_error "Download failed"
	exit 1
}

download_file "https://github.com/sabamdarif/Termux-AppStore/releases/download/files/websocketpp_${_websocketpp_version}_${archtype}.deb" || {
	print_failed "Failed to download websocketpp"
	progress_error "Download failed"
	exit 1
}

progress_phase "install" 50 "Installing packages..."

update_sys

progress_phase "install" 70 "Installing OBS Studio and dependencies..."
package_install_and_check "mbedtls luajit"
apt install ./*.deb -y 2>&1 | while IFS= read -r line; do
	echo "$line"
	if [[ "${line,,}" == *"unpacking"* ]]; then
		progress_phase "install" 80 "Unpacking packages..."
	elif [[ "${line,,}" == *"setting up"* ]]; then
		progress_phase "install" 90 "Setting up packages..."
	fi
done

install_status="${PIPESTATUS[0]}"

if [[ $install_status -ne 0 ]]; then
	print_failed "Installation failed"
	progress_error "Installation failed"
	cd ..
	check_and_delete "obs-studio-dl"
	exit 1
fi

progress_phase "cleanup" 95 "Cleaning up..."
cd ..
check_and_delete "obs-studio-dl"

print_success "OBS Studio installed successfully"
progress_done
