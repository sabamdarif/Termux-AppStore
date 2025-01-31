#!/data/data/com.termux/files/usr/bin/bash

supported_arch="arm64,arm"
version=4.10.2
app_type="distro"
supported_distro="all"
working_dir="${distro_path}/root"
page_url="https://github.com/SpacingBat3/WebCord"

app_arch=$(uname -m)
case "$app_arch" in
    aarch64) archtype="arm64" ;;
    armv7*|arm) archtype="armv7l" ;;
esac

if [[ "$archtype" == "armv7l" ]]; then
run_cmd="pdrun /opt/AppImageLauncher/Webcord/webcord --no-sandbox"
else
run_cmd="pdrun webcord --no-sandbox"
fi

if [[ "$archtype" == "armv7l" ]]; then
  cd ${distro_path}/opt/AppImageLauncher
  download_file "https://github.com/SpacingBat3/WebCord/releases/download/v${version}/webcord_${version}_${archtype}.AppImage"
  install_appimage "webcord_${version}_${archtype}.AppImage" "Webcord"
else
  if [[ "$selected_distro" == "debian" ]] || [[ "$selected_distro" == "ubuntu" ]];then
      cd $working_dir
      download_file "https://github.com/SpacingBat3/WebCord/releases/download/v${version}/webcord_${version}_${archtype}.deb"
      distro_run "apt install ./webcord_${version}_${archtype}.deb -y"
      distro_run "rm -f ./webcord_${version}_${archtype}.deb"
  elif [[ "$selected_distro" == "fedora" ]]; then
      cd $working_dir
      download_file "https://github.com/SpacingBat3/WebCord/releases/download/v${version}/webcord_${version}_${archtype}.rpm"
      distro_run "dnf install ./webcord_${version}_${archtype}.rpm -y"
      distro_run "rm -f ./webcord_${version}_${archtype}.rpm"
  fi
fi

print_success "Creating desktop entry..."
cat <<EOF | tee ${PREFIX}/share/applications/webcord.desktop >/dev/null
[Desktop Entry]
Name=Webcord
Exec=${run_cmd}
Terminal=false
Type=Application
Icon=webcord
StartupWMClass=webcord
Comment=Webcord
MimeType=x-scheme-handler/webcord;
Categories=Multimedia;
EOF