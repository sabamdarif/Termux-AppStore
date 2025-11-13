#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="zen-browser"
run_cmd="/opt/zen-browser/zen-browser --no-sandbox"
version="1.17.4b"
pause_update=true
app_type="distro"
supported_distro="all"
page_url="https://github.com/zen-browser/desktop"
working_dir="${distro_path}/opt"

# Check if a distro is selected
if [ -z "$selected_distro" ]; then
	print_failed "Error: No distro selected"
	exit 1
fi

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="aarch64" ;;
*) print_failed "Unsupported architectures" ;;
esac

filename="zen.linux-${archtype}.tar.xz"
temp_download="$TMPDIR/${filename}"
download_file "$temp_download" "${page_url}/releases/download/${version}/${filename}"

distro_run "
check_and_delete '/opt/zen-browser'
check_and_delete '/opt/zen'
"

if [[ "$selected_distro_type" == "chroot" ]]; then
	su -c "cp '$temp_download' '${working_dir}/${filename}'"
else
	cp "$temp_download" "${working_dir}/${filename}"
fi

distro_run "
cd /opt
extract '${filename}'
check_and_delete '${filename}'
mv -f zen zen-browser
cd /opt/zen-browser/
mv zen zen-browser
"

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee "${PREFIX}"/share/applications/pd_added/zen-browser.desktop >/dev/null
[Desktop Entry]
Name=Zen Browser
Comment=Experience tranquillity while browsing the web without people tracking you!
Exec=pdrun ${run_cmd}
Icon=${HOME}/.appstore/logo/zen-browser/logo.png
Type=Application
MimeType=text/html;text/xml;application/xhtml+xml;x-scheme-handler/http;x-scheme-handler/https;application/x-xpinstall;application/pdf;application/json;
StartupWMClass=zen-beta
Categories=Network;WebBrowser;
StartupNotify=true
Terminal=false
DESKTOP_EOF
