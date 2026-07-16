#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="refine"
run_cmd="refine"
version="0.5.10"
app_type="native"

# SHA256 of downloaded artifact(s); verified by download_file (Part C-bis).
declare -A sha256=(
	["refine_0.5.10_aarch64.deb"]="ac0f22e80a2028cf3919f3d54ad032c7f77d3b7680fc4eca3425eb80c0248893"
	["refine_0.5.10_arm.deb"]="9813db2ee5610467a908450ed17fb146a6e51e8104d80fe1d0011640aeacbcc6"
)

archtype=$(detect_arch aarch64=aarch64 'armv7*=arm' arm=arm armv8l=arm)
deb_file_name="refine_${version}_${archtype}.deb"
install_deb_into_termux "https://github.com/sabamdarif/Termux-AppStore/releases/download/files/${deb_file_name}"
