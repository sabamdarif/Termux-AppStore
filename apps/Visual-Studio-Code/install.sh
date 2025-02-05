#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="code"
version=distro_local_version
app_type="distro"
supported_distro="all"
# working_dir="${distro_path}"
package_name="code"
run_cmd="pdrun /usr/share/code/code --no-sandbox"

if [[ "$selected_distro" == "debian" ]] || [[ "$selected_distro" == "ubuntu" ]];then
    distro_run "apt install wget gpg -y"
    distro_run 'wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor | tee /etc/apt/keyrings/packages.microsoft.gpg >/dev/null && echo "deb [arch=amd64,arm64,armhf signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main" | tee /etc/apt/sources.list.d/vscode.list >/dev/null'
    distro_run "rm -f packages.microsoft.gpg"
    distro_run "apt install apt-transport-https -y"
    distro_run "apt update -y"
    $selected_distro install code -y
elif [[ "$selected_distro" == "fedora" ]]; then
    distro_run 'rpm --import https://packages.microsoft.com/keys/microsoft.asc && echo -e "[code]\nname=Visual Studio Code\nbaseurl=https://packages.microsoft.com/yumrepos/vscode\nenabled=1\ngpgcheck=1\ngpgkey=https://packages.microsoft.com/keys/microsoft.asc" | tee /etc/yum.repos.d/vscode.repo > /dev/null'
    distro_run "dnf check-update -y"
    $selected_distro install code -y
fi
sed -i 's|Exec=pdrun code|Exec=pdrun /usr/share/code/code --no-sandbox|g' "/data/data/com.termux/files/usr/share/applications/code.desktop"