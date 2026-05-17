#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
run_cmd="/opt/Signal-Unofficial/signal-desktop-unofficial --no-sandbox"
version="v8.10.0"
app_type="distro"
supported_distro="all"
page_url="https://github.com/dennisameling/Signal-Desktop"
working_dir="${distro_path}/root"

progress_phase "prepare" 0 "Preparing..."

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="arm64" ;;
*) print_failed "Unsupported architectures" ;;
esac

if [[ "$SELECTED_DISTRO" == "ubuntu" ]] || [[ "$SELECTED_DISTRO" == "debian" ]]; then
	progress_phase "configure" 0 "Configuring..."
	filename="signal-desktop-unofficial_${version#v}_${archtype}.deb"
	temp_download="$TMPDIR/${filename}"
	progress_phase "download" 0 "Downloading..."
	download_file "$temp_download" "${page_url}/releases/download/${version}/${filename}"
	pd_check_and_delete "/root/${filename}"
	"${SELECTED_DISTRO_TYPE}"-distro login "$SELECTED_DISTRO" -- cp "$temp_download" "/root/${filename}"
	pd_update_sys
	distro_run "
apt install /root/${filename} -y
cd /opt
mv 'Signal Unofficial' Signal-Unofficial
"
	pd_check_and_delete "/root/${filename}"

elif [[ "$SELECTED_DISTRO" == "fedora" ]]; then
	progress_phase "configure" 0 "Configuring..."
	filename="signal-desktop-unofficial_${version#v}_${archtype}.deb"
	temp_download="$TMPDIR/${filename}"
	progress_phase "download" 0 "Downloading..."
	pd_check_and_delete '/root/signal'
	pd_check_and_delete "/root/${filename}"

	"${SELECTED_DISTRO_TYPE}"-distro login "$SELECTED_DISTRO" -- cp "$temp_download" "/root/${filename}"
	pd_update_sys
	pd_package_install_and_check --just "ar atk dbus-libs libnotify libXtst nss alsa-lib pulseaudio-libs libXScrnSaver glibc gtk3 mesa-libgbm libX11-xcb libappindicator-gtk3"
	distro_run "
cd /root
mkdir signal
mv ${filename} signal/
cd signal
ar x ${filename}
extract 'data.tar.xz'
cd opt
mv 'Signal Unofficial' /opt/Signal-Unofficial
cd /root
check_and_delete 'signal'
"
else
	print_failed "Unsupported distro"
fi

progress_phase "desktop" 0 "Creating desktop entry..."
print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee "${TERMUX_PREFIX}"/share/applications/pd_added/signal-desktop-unofficial.desktop >/dev/null
[Desktop Entry]
Name=Signal Unofficial
Exec=pdrun ${run_cmd}
Terminal=false
Type=Application
Icon=${HOME}/.appstore/logo/signal-desktop-unofficial/logo.png
StartupWMClass=signal-desktop-unofficial
Comment=Private messaging from your desktop (UNOFFICIAL)
MimeType=x-scheme-handler/sgnl;x-scheme-handler/signalcaptcha;
Categories=Network;InstantMessaging;Chat;
DESKTOP_EOF

progress_done
