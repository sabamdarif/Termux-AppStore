#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="spotube"
run_cmd="/opt/spotube/spotube --no-sandbox"
version="v3.9.0"
pause_update=true
app_type="distro"
page_url="https://github.com/KRTirtho/spotube"
working_dir="${distro_path}/opt"
supported_distro="all"

# Check if a distro is selected
if [ -z "$selected_distro" ]; then
    print_failed "Error: No distro selected"
    exit 1
fi

if [[ "$selected_distro" == "debian" ]] || [[ "$selected_distro" == "ubuntu" ]]; then
distro_run "
sudo apt update && sudo apt install -y libayatana-appindicator3-1 libwebkit2gtk-4.0-37 libavcodec-extra libasound2 libegl1-mesa libgl1-mesa-glx libgles2 libwayland-egl1 libx11-xcb1 libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 mpv libmpv-dev libxcb-xfixes0 pipewire pipewire-audio-client-libraries libgtk-3-0 libgdk-pixbuf2.0-0 libwayland-client0 libwayland-egl1 libwayland-cursor0
"

elif [[ "$selected_distro" == "fedora" ]]; then
distro_run "
sudo dnf install -y libayatana-appindicator webkit2gtk3 ffmpeg alsa-lib mesa-libEGL mesa-libGL mesa-libGLES wayland libX11-xcb libXcomposite libXcursor libXdamage libXext libXfixes libXi libXrandr libXrender mpv mpv-libs libxcb pipewire pipewire-libs pipewire-alsa pipewire-pulseaudio gtk3 gdk-pixbuf2 wayland-devel
"
fi


distro_run "
check_and_delete '/opt/spotube'
check_and_create_directory '/opt/spotube'
"
cd $working_dir/spotube
echo "$(pwd)"
download_file "${page_url}/releases/download/${version}/spotube-linux-${version#v}-${supported_arch}.tar.xz"
distro_run "
cd /opt/spotube
echo "$(pwd)"
extract "spotube-linux-${version#v}-${supported_arch}.tar.xz"
check_and_delete "spotube-linux-${version#v}-${supported_arch}.tar.xz"
"
print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${PREFIX}/share/applications/pd_added/spotube.desktop >/dev/null
[Desktop Entry]
Name=Spotube
Exec=pdrun ${run_cmd}
Terminal=false
Type=Application
Icon=${HOME}/.appstore/logo/Spotube/logo.png
StartupWMClass=spotube
Comment=Open source Spotify client
MimeType=x-scheme-handler/spotube;
Categories=Internet;
DESKTOP_EOF

