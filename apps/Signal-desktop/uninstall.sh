#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing signal-desktop-unofficial..."

distro_run "
mv /opt/Signal-Unofficial '/opt/Signal Unofficial'
"
if [[ "$SELECTED_DISTRO" == "ubuntu" ]] || [[ "$SELECTED_DISTRO" == "debian" ]]; then
	pd_package_remove_and_check "signal-desktop-unofficial"
elif [[ "$SELECTED_DISTRO" == "fedora" ]]; then
	pd_check_and_delete "/opt/Signal-Unofficial"
else
	print_failed "Unsupported distro"
fi
check_and_delete "${TERMUX_PREFIX}/share/applications/pd_added/signal-desktop-unofficial.desktop"

progress_done
