#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
# version=2.34.1
app_type="distro"
supported_distro="all"
# working_dir=""
run_cmd="libreoffice"

if [[ "$selected_distro" == "debian" ]] || [[ "$selected_distro" == "ubuntu" ]];then
  $selected_distro install libreoffice -y
elif [[ "$selected_distro" == "fedora" ]]; then
  $selected_distro install libreoffice -y
fi