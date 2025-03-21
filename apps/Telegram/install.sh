#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
version=distro_local_version
app_type="distro"
supported_distro="fedora,debian"
# working_dir=""
package_name="telegram-desktop"
run_cmd="telegram-desktop --no-sandbox"

if [[ "$selected_distro" == "debian" ]] || [[ "$selected_distro" == "ubuntu" ]];then
distro_run "
sudo apt update -y -o Dpkg::Options::="--force-confnew"
"
    $selected_distro install telegram-desktop -y
elif [[ "$selected_distro" == "fedora" ]]; then
    distro_run 'dnf install https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(. /etc/os-release && echo $VERSION_ID).noarch.rpm -y'
    $selected_distro install telegram-desktop -y
fi

if [[ "$selected_distro" == "debian" ]];then
    fix_exec "pd_added/org.telegram.desktop.desktop" "--no-sandbox"
else
    fix_exec "pd_added/telegram-desktop.desktop" "--no-sandbox"
fi