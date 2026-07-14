#!/data/data/com.termux/files/usr/bin/bash
supported_arch="aarch64,arm"
run_cmd="github-desktop --no-sandbox"
version="release-3.4.13-linux1"
final_version="${version#release-}"
app_type="distro"
supported_distro="all"
page_url="https://github.com/shiftkey/desktop"
working_dir="${distro_path}/root"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
declare -A sha256=(
	["GitHubDesktop-linux-aarch64-3.4.13-linux1.rpm"]="8914f985013da02e36de63b65fc252dc86fd9326497f0cf3f49402017fe1006f"
	["GitHubDesktop-linux-arm64-3.4.13-linux1.deb"]="48de2ab44238abf00081f51a062339796c822b92abefb0ab4c7b08026bc471e5"
	["GitHubDesktop-linux-armv7l-3.4.13-linux1.rpm"]="e7245fc83d8f7a4be854e43e6441c6932d7d4702dfa3b38cf16c56442ed295a1"
)

progress_phase "prepare" 0 "Preparing..."

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="arm64" ;;
armv7* | arm) archtype="armv7l" ;;
*) print_failed "Unsupported architectures" ;;
esac

if [[ "$SELECTED_DISTRO" == "ubuntu" ]] || [[ "$SELECTED_DISTRO" == "debian" ]]; then
	progress_phase "configure" 0 "Configuring..."
	filename="GitHubDesktop-linux-${archtype}-${final_version}.deb"
	temp_download="$TMPDIR/${filename}"
	progress_phase "download" 0 "Downloading..."
	download_file "$temp_download" "${page_url}/releases/download/${version}/${filename}"
	pd_check_and_delete "/root/${filename}"
	"${SELECTED_DISTRO_TYPE}"-distro login "$SELECTED_DISTRO" -- cp "$temp_download" "/root/${filename}"
	pd_update_sys
	distro_run "sudo apt install /root/${filename} -y"
	pd_check_and_delete "/root/${filename}"
elif [[ "$SELECTED_DISTRO" == "fedora" ]]; then
	progress_phase "configure" 0 "Configuring..."
	if [[ "$archtype" == "armv7l" ]]; then
		filename="GitHubDesktop-linux-${archtype}-${final_version}.rpm"
	else
		filename="GitHubDesktop-linux-${app_arch}-${final_version}.rpm"
	fi
	temp_download="$TMPDIR/${filename}"
	progress_phase "download" 0 "Downloading..."
	download_file "$temp_download" "${page_url}/releases/download/${version}/${filename}"
	pd_check_and_delete "/root/${filename}"
	"${SELECTED_DISTRO_TYPE}"-distro login "$SELECTED_DISTRO" -- cp "$temp_download" "/root/${filename}"
	distro_run "dnf install /root/${filename} -y"
	pd_check_and_delete "/root/${filename}"

else
	print_failed "Unsupported distro"
fi

progress_phase "desktop" 0 "Creating desktop entry..."
print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee "${TERMUX_PREFIX}"/share/applications/pd_added/github-desktop.desktop >/dev/null
[Desktop Entry]
Name=GitHub Desktop
Exec=pdrun ${run_cmd}
Terminal=false
Type=Application
Icon=${HOME}/.appstore/logo/github-desktop/logo.png
StartupWMClass=GitHub Desktop
Comment=Simple collaboration from your desktop
Categories=Development;RevisionControl;
DESKTOP_EOF

progress_done
