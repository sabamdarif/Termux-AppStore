#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="cursor"
version=distro_local_version
app_type="distro"
supported_distro="all"
run_cmd="cursor --no-sandbox"

if [[ "$selected_distro" == "debian" ]] || [[ "$selected_distro" == "ubuntu" ]]; then

	distro_run '
mkdir -p /etc/apt/keyrings
apt update
apt install gpg -y
curl -fsSL https://downloads.cursor.com/keys/anysphere.asc | gpg --dearmor | sudo tee /etc/apt/keyrings/cursor.gpg > /dev/null
echo "deb [arch=amd64,arm64 signed-by=/etc/apt/keyrings/cursor.gpg] https://downloads.cursor.com/aptrepo stable main" | sudo tee /etc/apt/sources.list.d/cursor.list > /dev/null
apt update
'

elif [[ "$selected_distro" == "fedora" ]]; then
	distro_run '
tee /etc/yum.repos.d/antigravity.repo << EOL
[cursor]
name=Cursor
baseurl=https://downloads.cursor.com/yumrepo
enabled=1
gpgcheck=1
gpgkey=https://downloads.cursor.com/keys/anysphere.asc
EOL
dnf makecache
'
fi

$selected_distro install $package_name -y

fix_exec "pd_added/$package_name.desktop" "--no-sandbox"
fix_exec "pd_added/$package_name-url-handler.desktop" "--no-sandbox" 2>/dev/null || true
