#!/data/data/com.termux/files/usr/bin/bash
supported_arch="aarch64,arm"
run_cmd="github-desktop --no-sandbox"
version="release-3.4.13-linux1"
final_version="${version#release-}"
app_type="distro"
supported_distro="all"
page_url="https://github.com/shiftkey/desktop"
working_dir="${distro_path}/root"

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="arm64" ;;
armv7* | arm) archtype="armv7l" ;;
*) print_failed "Unsupported architectures" ;;
esac

if [[ "$selected_distro" == "ubuntu" ]] || [[ "$selected_distro" == "debian" ]]; then
	filename="GitHubDesktop-linux-${archtype}-${final_version}.deb"
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
check_and_delete '/root/${filename}'
"
elif [[ "$selected_distro" == "fedora" ]]; then
	if [[ "$archtype" == "armv7l" ]]; then
		filename="GitHubDesktop-linux-${archtype}-${final_version}.rpm"
	else
		filename="GitHubDesktop-linux-${app_arch}-${final_version}.rpm"
	fi
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
sudo dnf install /root/${filename} -y
check_and_delete '/root/${filename}'
"
else
	print_failed "Unsupported distro"
fi

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee "${PREFIX}"/share/applications/pd_added/github-desktop.desktop >/dev/null
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
