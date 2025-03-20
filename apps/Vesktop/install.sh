#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="vesktop"
run_cmd="vesktop --no-sandbox"
version="v1.5.4"
pause_update=true
app_type="distro"
supported_distro="all"
page_url="https://github.com/Vencord/Vesktop"
working_dir="${distro_path}/root"

if [[ "$selected_distro" == "ubuntu" ]] || [[ "$selected_distro" == "debian" ]]; then
cd $working_dir
filename="vesktop_${version#v}_arm64.deb"
distro_run "
check_and_delete "/root/${filename}"
"
download_file "${page_url}/releases/download/${version}/${filename}"
distro_run "
sudo apt update -y -o Dpkg::Options::="--force-confnew"
sudo apt install ./${filename} -y
check_and_delete "/root/${filename}"
"
elif [[ "$selected_distro" == "fedora" ]]; then
cd $working_dir
filename="vesktop_${version#v}_aarch64.rpm"
distro_run "
check_and_delete "/root/${filename}"
"
download_file "${page_url}/releases/download/${version}/${filename}"
distro_run "
sudo dnf install ./${filename} -y
check_and_delete "/root/${filename}"
"
else
    print_failed "Unsupported distro"
fi

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${PREFIX}/share/applications/pd_added/vesktop.desktop >/dev/null
[Desktop Entry]
Name=Vesktop
Exec=${run_cmd} --no-sandbox
Terminal=false
Type=Application
Icon=${HOME}/.appstore/logo/vesktop/logo.png
StartupWMClass=vesktop
Comment=Vesktop is a custom Discord App
MimeType=x-scheme-handler/sgnl;x-scheme-handler/signalcaptcha;
Categories=Network;InstantMessaging;Chat;
DESKTOP_EOF
