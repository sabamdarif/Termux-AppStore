#!/data/data/com.termux/files/usr/bin/bash

# remove based on distro type
case "$SELECTED_DISTRO" in
"debian" | "ubuntu")
	pd_package_remove_and_check "libreoffice libreoffice-gtk3"
	;;
"fedora")
	pd_package_remove_and_check libreoffice
	;;
"arch*")
	pd_package_remove_and_check libreoffice-fresh
	;;
*)
	echo "Unsupported distribution: $SELECTED_DISTRO"
	exit 1
	;;
esac

