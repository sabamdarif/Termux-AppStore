#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
run_cmd="/opt/Signal-Unofficial/signal-desktop-unofficial --no-sandbox"
version="v7.90.0"
app_type="distro"
supported_distro="all"
page_url="https://github.com/dennisameling/Signal-Desktop"
working_dir="${distro_path}/root"

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="arm64" ;;
*) print_failed "Unsupported architectures" ;;
esac

if [[ "$selected_distro" == "ubuntu" ]] || [[ "$selected_distro" == "debian" ]]; then
	filename="signal-desktop-unofficial_${version#v}_${archtype}.deb"
	temp_download="$TMPDIR/${filename}"
	download_file "$temp_download" "${page_url}/releases/download/${version}/${filename}"
	distro_run "
check_and_delete '/root/${filename}'
"
	if [[ "$selected_distro_type" == "chroot" ]]; then
		su -c "cp '$temp_download' '${working_dir}/${filename}'"
	else
		cp "$temp_download" "${working_dir}/${filename}"
	fi
	distro_run "
sudo apt update -y -o Dpkg::Options::='--force-confnew'
sudo apt install /root/${filename} -y
cd /opt
mv 'Signal Unofficial' Signal-Unofficial
check_and_delete '/root/${filename}'
"
elif [[ "$selected_distro" == "fedora" ]]; then
	filename="signal-desktop-unofficial_${version#v}_${archtype}.deb"
	temp_download="$TMPDIR/${filename}"
	download_file "$temp_download" "${page_url}/releases/download/${version}/${filename}"
	distro_run "
check_and_delete '/root/signal'
check_and_delete '/root/${filename}'
"
	if [[ "$selected_distro_type" == "chroot" ]]; then
		su -c "cp '$temp_download' '${working_dir}/${filename}'"
	else
		cp "$temp_download" "${working_dir}/${filename}"
	fi
	distro_run "
cd /root
mkdir signal
mv ${filename} signal/
cd signal
sudo dnf install -y ar atk dbus-libs libnotify libXtst nss alsa-lib pulseaudio-libs libXScrnSaver glibc gtk3 mesa-libgbm libX11-xcb libappindicator-gtk3
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

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee "${PREFIX}"/share/applications/pd_added/signal-desktop-unofficial.desktop >/dev/null
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
