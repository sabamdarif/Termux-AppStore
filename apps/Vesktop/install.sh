#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="vesktop"
run_cmd="vesktop --no-sandbox"
version="v1.6.5"
pause_update=true
app_type="distro"
supported_distro="all"
page_url="https://github.com/Vencord/Vesktop"
working_dir="${distro_path}/root"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
sha256="3ba8e5b14d4eafa641f407c8720fb0ec489a9ee6276423f98e967218b5d6cd38"

if [[ "$SELECTED_DISTRO" == "fedora" ]]; then
	filename="vesktop_${version#v}_aarch64.rpm"
else
	filename="vesktop_${version#v}_arm64.deb"
fi

install_deb_into_distro "${page_url}/releases/download/${version}/${filename}" "${filename}"

create_desktop_entry \
	--name "Vesktop" --pkg "vesktop" --logo-dir "vesktop" \
	--exec "${run_cmd}" \
	--wmclass "vesktop" \
	--comment "Vesktop is a custom Discord App" \
	--categories "Network;InstantMessaging;Chat;" \
	--mime "x-scheme-handler/sgnl;x-scheme-handler/signalcaptcha;"
