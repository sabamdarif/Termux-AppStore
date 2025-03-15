#!/data/data/com.termux/files/usr/bin/bash

distro_run "
mv /opt/Signal-Unofficial '/opt/Signal Unofficial'
"
if [[ "$selected_distro" == "ubuntu" ]] || [[ "$selected_distro" == "debian" ]]; then
distro_run "
sudo apt remove signal-desktop-unofficial -y
"
elif [[ "$selected_distro" == "fedora" ]]; then
distro_run "
rm -rf "/opt/Signal Unofficial"
"
else
    print_failed "Unsupported distro"
fi
check_and_delete "${PREFIX}/share/applications/pd_added/signal-desktop-unofficial.desktop"