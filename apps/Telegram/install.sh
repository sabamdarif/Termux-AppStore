#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
# version=2.34.1
app_type="distro"
supported_distro="all"
# working_dir=""
run_cmd="telegram-desktop"

if [[ "$selected_distro" == "debian" ]] || [[ "$selected_distro" == "ubuntu" ]];then
    $selected_distro install telegram-desktop -y
elif [[ "$selected_distro" == "fedora" ]]; then
    distro_run 'dnf install https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(. /etc/os-release && echo $VERSION_ID).noarch.rpm -y'
    $selected_distro install telegram-desktop -y
fi

fix_exec "telegram-desktop.desktop" "--no-sandbox"