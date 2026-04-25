#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="antigravity"
version=distro_local_version
app_type="distro"
supported_distro="all"
run_cmd="antigravity --no-sandbox"

if [[ "$SELECTED_DISTRO" == "debian" ]] || [[ "$SELECTED_DISTRO" == "ubuntu" ]]; then

	pd_check_and_create_directory "/etc/apt/keyrings"
	pd_update_sys
	pd_package_install_and_check --just "gpg"
	distro_run '
curl -fsSL https://us-central1-apt.pkg.dev/doc/repo-signing-key.gpg | gpg --dearmor --yes -o /etc/apt/keyrings/antigravity-repo-key.gpg
echo "deb [signed-by=/etc/apt/keyrings/antigravity-repo-key.gpg] https://us-central1-apt.pkg.dev/projects/antigravity-auto-updater-dev/ antigravity-debian main" | tee /etc/apt/sources.list.d/antigravity.list > /dev/null
'
	pd_update_sys

elif [[ "$SELECTED_DISTRO" == "fedora" ]]; then
	pd_check_and_create_directory "/etc/yum.repos.d"
	distro_run '
tee /etc/yum.repos.d/antigravity.repo << EOL
[antigravity-rpm]
name=Antigravity RPM Repository
baseurl=https://us-central1-yum.pkg.dev/projects/antigravity-auto-updater-dev/antigravity-rpm
enabled=1
gpgcheck=0
EOL
'
	pd_update_sys
fi

pd_package_install_and_check "$package_name"
fix_exec "pd_added/$package_name.desktop" "--no-sandbox"
fix_exec "pd_added/$package_name-url-handler.desktop" "--no-sandbox"
