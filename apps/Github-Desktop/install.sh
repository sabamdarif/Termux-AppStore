#!/data/data/com.termux/files/usr/bin/bash
supported_arch="aarch64,arm"
run_cmd="github-desktop --no-sandbox"
version="release-3.4.13-linux1"
final_version="${version#release-}"
app_type="distro"
supported_distro="all"
page_url="https://github.com/shiftkey/desktop"
working_dir="${distro_path}/root"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
declare -A sha256=(
	["GitHubDesktop-linux-aarch64-3.4.13-linux1.rpm"]="8914f985013da02e36de63b65fc252dc86fd9326497f0cf3f49402017fe1006f"
	["GitHubDesktop-linux-arm64-3.4.13-linux1.deb"]="48de2ab44238abf00081f51a062339796c822b92abefb0ab4c7b08026bc471e5"
	["GitHubDesktop-linux-armv7l-3.4.13-linux1.rpm"]="e7245fc83d8f7a4be854e43e6441c6932d7d4702dfa3b38cf16c56442ed295a1"
)

if [[ "$SELECTED_DISTRO" == "fedora" ]]; then
	rpmarch=$(detect_arch aarch64=aarch64 'armv7*=armv7l' arm=armv7l)
	filename="GitHubDesktop-linux-${rpmarch}-${final_version}.rpm"
else
	debarch=$(detect_arch aarch64=arm64 'armv7*=armv7l' arm=armv7l)
	filename="GitHubDesktop-linux-${debarch}-${final_version}.deb"
fi

install_deb_into_distro "${page_url}/releases/download/${version}/${filename}" "${filename}"

create_desktop_entry \
	--name "GitHub Desktop" --pkg "github-desktop" --logo-dir "github-desktop" \
	--exec "${run_cmd}" \
	--wmclass "GitHub Desktop" \
	--comment "Simple collaboration from your desktop" \
	--categories "Development;RevisionControl;"
