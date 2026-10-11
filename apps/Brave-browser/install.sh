#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="brave-browser"
run_cmd="/opt/brave-browser/brave-browser --no-sandbox"
version="v1.97.56"
app_type="distro"
page_url="https://github.com/brave/brave-browser"
working_dir="${distro_path}/opt"
supported_distro="all"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
sha256="f18823bfe8bf626a7412a2cc142ba851f991665ca31af8d750f80dbb8371f984"

if [ -z "$SELECTED_DISTRO" ]; then
	print_failed "Error: No distro selected"
fi

install_archive_into_opt "brave-browser" \
	"${page_url}/releases/download/${version}/brave-browser-${version#v}-linux-arm64.zip"

create_desktop_entry \
	--name "Brave-browser" --pkg "brave-browser" \
	--exec "${run_cmd}" \
	--wmclass "brave-browser" \
	--comment "Brave is a free and open-source web browser" \
	--categories "Internet;" \
	--mime "x-scheme-handler/brave-browser;"
