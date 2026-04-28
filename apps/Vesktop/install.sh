#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="vesktop"
run_cmd="vesktop --no-sandbox"
version="v1.6.5"
pause_update=true
app_type="distro"
supported_distro="all"
page_url="https://github.com/Vencord/Vesktop"
working_dir="${distro_path}/root"

progress_phase "prepare" 0 "Preparing..."

if [[ "$SELECTED_DISTRO" == "ubuntu" ]] || [[ "$SELECTED_DISTRO" == "debian" ]]; then
	progress_phase "configure" 0 "Configuring..."
	filename="vesktop_${version#v}_arm64.deb"
	temp_download="$TMPDIR/${filename}"
	progress_phase "download" 0 "Downloading..."
	download_file "$temp_download" "${page_url}/releases/download/${version}/${filename}"
	pd_check_and_delete "/root/${filename}"
	"${SELECTED_DISTRO_TYPE}"-distro login "$SELECTED_DISTRO" -- cp "$temp_download" "/root/${filename}"
	pd_update_sys
	pd_check_and_delete "/root/${filename}"

elif [[ "$SELECTED_DISTRO" == "fedora" ]]; then
	progress_phase "configure" 0 "Configuring..."
	filename="vesktop_${version#v}_aarch64.rpm"
	temp_download="$TMPDIR/${filename}"
	progress_phase "download" 0 "Downloading..."
	download_file "$temp_download" "${page_url}/releases/download/${version}/${filename}"
	pd_check_and_delete "/root/${filename}"
	"${SELECTED_DISTRO_TYPE}"-distro login "$SELECTED_DISTRO" -- cp "$temp_download" "/root/${filename}"
	distro_run "
dnf install /root/${filename} -y
"
	pd_check_and_delete "/root/${filename}"

else
	print_failed "Unsupported distro"
fi

progress_phase "desktop" 0 "Creating desktop entry..."
print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee "${TERMUX_PREFIX}"/share/applications/pd_added/vesktop.desktop >/dev/null
[Desktop Entry]
Name=Vesktop
Exec=pdrun ${run_cmd} --no-sandbox
Terminal=false
Type=Application
Icon=${HOME}/.appstore/logo/vesktop/logo.png
StartupWMClass=vesktop
Comment=Vesktop is a custom Discord App
MimeType=x-scheme-handler/sgnl;x-scheme-handler/signalcaptcha;
Categories=Network;InstantMessaging;Chat;
DESKTOP_EOF

progress_done
