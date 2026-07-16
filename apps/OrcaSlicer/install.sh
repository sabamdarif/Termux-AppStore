#!/data/data/com.termux/files/usr/bin/bash

supported_arch="arm64"
version="V2.3.0"
app_type="distro"
supported_distro="ubuntu,debian"
working_dir="${distro_path}/root"
page_url="https://github.com/CodeMasterCody3D/OrcaSlicer"
run_cmd="orca-slicer"

# ponytail: upstream fork has zero releases (artifacts 404) — intentionally
# unpinned; fails at the missing-hash check until the user picks a real source.
sha256="skip"

if [[ "$SELECTED_DISTRO" != "ubuntu" && "$SELECTED_DISTRO" != "debian" ]]; then
	print_failed "OrcaSlicer is only supported on Ubuntu/Debian"
fi

filename="OrcaSlicer_UbuntuLinux_${version}-dev${supported_arch}.deb"
install_deb_into_distro "${page_url}/releases/download/${supported_arch}/${filename}" "${filename}"

create_desktop_entry \
	--name "OrcaSlicer" --pkg "OrcaSlicer" --logo-dir "OrcaSlicer" \
	--exec "${run_cmd}" \
	--comment "OrcaSlicer" \
	--categories "Graphics;3DPrinting;"
