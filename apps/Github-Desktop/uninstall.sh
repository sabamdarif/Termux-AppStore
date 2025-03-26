#!/data/data/com.termux/files/usr/bin/bash

if [[ "$selected_distro" == "ubuntu" ]] || [[ "$selected_distro" == "debian" ]]; then
    distro_run "apt remove github-desktop -y"
elif [[ "$selected_distro" == "fedora" ]]; then
    distro_run "dnf remove github-desktop -y"
fi
check_and_delete "${PREFIX}/share/applications/github-desktop.desktop"