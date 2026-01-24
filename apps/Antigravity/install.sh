#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="antigravity"
version=distro_local_version
app_type="distro"
supported_distro="all"
run_cmd="antigravity --no-sandbox"

if [[ "$selected_distro" == "debian" ]] || [[ "$selected_distro" == "ubuntu" ]]; then

	distro_run '
sudo mkdir -p /etc/apt/keyrings
sudo apt update
sudo apt install gpg -y
curl -fsSL https://us-central1-apt.pkg.dev/doc/repo-signing-key.gpg | sudo gpg --dearmor --yes -o /etc/apt/keyrings/antigravity-repo-key.gpg
echo "deb [signed-by=/etc/apt/keyrings/antigravity-repo-key.gpg] https://us-central1-apt.pkg.dev/projects/antigravity-auto-updater-dev/ antigravity-debian main" | sudo tee /etc/apt/sources.list.d/antigravity.list > /dev/null
sudo apt update
'

elif [[ "$selected_distro" == "fedora" ]]; then
	distro_run '
sudo tee /etc/yum.repos.d/antigravity.repo << EOL
[antigravity-rpm]
name=Antigravity RPM Repository
baseurl=https://us-central1-yum.pkg.dev/projects/antigravity-auto-updater-dev/antigravity-rpm
enabled=1
gpgcheck=0
EOL
sudo dnf makecache
'
fi

$selected_distro install $package_name -y

fix_exec "pd_added/$package_name.desktop" "--no-sandbox"
fix_exec "pd_added/$package_name-url-handler.desktop" "--no-sandbox"
