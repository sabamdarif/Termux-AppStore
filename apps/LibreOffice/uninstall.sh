#!/data/data/com.termux/files/usr/bin/bash

if [[ "$selected_distro" == "debian" ]] || [[ "$selected_distro" == "ubuntu" ]];then
  $selected_distro remove libreoffice -y
elif [[ "$selected_distro" == "fedora" ]]; then
  $selected_distro remove libreoffice -y
fi