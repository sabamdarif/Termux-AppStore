#!/data/data/com.termux/files/usr/bin/bash

supported_arch="arm64"
version=v4.10.3
app_type="distro"
supported_distro="fedora,ubuntu,debian"
working_dir="${distro_path}/root"
page_url="https://github.com/SpacingBat3/WebCord"
run_cmd="webcord --no-sandbox"

if [[ "$selected_distro" == "debian" ]] || [[ "$selected_distro" == "ubuntu" ]];then
    cd $working_dir
    download_file "${page_url}/releases/download/${version}/webcord_${version#v}_${supported_arch}.deb"
    distro_run "apt install ./webcord_${version#v}_${supported_arch}.deb -y"
    distro_run "rm -f webcord_${version#v}_${supported_arch}.deb"
elif [[ "$selected_distro" == "fedora" ]]; then
    cd $working_dir
    download_file "${page_url}/releases/download/${version}/webcord_${version#v}_${supported_arch}.rpm"
    distro_run "dnf install ./webcord_${version#v}_${supported_arch}.rpm -y"
    distro_run "rm -f webcord_${version#v}_${supported_arch}.rpm"
fi

print_success "Creating desktop entry..."
cat <<EOF | tee ${PREFIX}/share/applications/webcord.desktop >/dev/null
[Desktop Entry]
Name=Webcord
Exec=pdrun ${run_cmd}
Terminal=false
Type=Application
Icon=webcord
StartupWMClass=webcord
Comment=Webcord
MimeType=x-scheme-handler/webcord;
Categories=Multimedia;
EOF