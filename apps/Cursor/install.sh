#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="cursor"
version=distro_local_version
app_type="distro"
supported_distro="all"
run_cmd="cursor --no-sandbox"

if [[ "$SELECTED_DISTRO" == "debian" ]] || [[ "$SELECTED_DISTRO" == "ubuntu" ]]; then

	pd_check_and_create_directory "/etc/apt/keyrings"
	pd_update_sys
	pd_package_install_and_check --just "gpg"
	distro_run '
curl -fsSL https://downloads.cursor.com/keys/anysphere.asc | gpg --dearmor | tee /etc/apt/keyrings/cursor.gpg > /dev/null
echo "deb [arch=amd64,arm64 signed-by=/etc/apt/keyrings/cursor.gpg] https://downloads.cursor.com/aptrepo stable main" | tee /etc/apt/sources.list.d/cursor.list > /dev/null
'
	pd_update_sys

elif [[ "$SELECTED_DISTRO" == "fedora" ]]; then
	pd_check_and_create_directory "/etc/yum.repos.d"
	distro_run '
tee /etc/yum.repos.d/antigravity.repo << EOL
[cursor]
name=Cursor
baseurl=https://downloads.cursor.com/yumrepo
enabled=1
gpgcheck=1
gpgkey=https://downloads.cursor.com/keys/anysphere.asc
EOL
'
	pd_update_sys
fi

pd_package_install_and_check "$package_name"
fix_exec "pd_added/$package_name.desktop" "--no-sandbox"
fix_exec "pd_added/$package_name-url-handler.desktop" "--no-sandbox" 2>/dev/null || true
