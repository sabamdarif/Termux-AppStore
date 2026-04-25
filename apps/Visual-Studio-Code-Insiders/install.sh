#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="code-insiders"
version=distro_local_version
app_type="distro"
supported_distro="all"
# working_dir="${distro_path}"
run_cmd="/usr/share/code-insiders/code-insiders --no-sandbox"

if [[ "$SELECTED_DISTRO" == "debian" ]] || [[ "$SELECTED_DISTRO" == "ubuntu" ]]; then

	distro_run '
apt update -y -o Dpkg::Options::="--force-confnew"

apt-get install -y wget gpg apt-transport-https

wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor | tee /etc/apt/keyrings/packages.microsoft.gpg > /dev/null

install -D -o root -g root -m 644 /etc/apt/keyrings/packages.microsoft.gpg /etc/apt/keyrings/packages.microsoft.gpg

echo "deb [arch=amd64,arm64,armhf signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main" | tee /etc/apt/sources.list.d/vscode.list > /dev/null
'
	pd_package_install_and_check "$package_name"

elif [[ "$SELECTED_DISTRO" == "fedora" ]]; then
	distro_run '
rpm --import https://packages.microsoft.com/keys/microsoft.asc

echo -e "[code]\nname=Visual Studio Code\nbaseurl=https://packages.microsoft.com/yumrepos/vscode\nenabled=1\ngpgcheck=1\ngpgkey=https://packages.microsoft.com/keys/microsoft.asc" | tee /etc/yum.repos.d/vscode.repo > /dev/null
'
	pd_package_install_and_check "$package_name"
else
	print_failed "Unsupported Distro"
	exit 1
fi

fix_exec "pd_added/$package_name.desktop" "--no-sandbox"
