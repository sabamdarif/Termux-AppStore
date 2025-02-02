#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
version=release-3.4.8-linux1
app_type="distro"
supported_distro="all"
working_dir="${distro_path}/root"
page_url="https://github.com/shiftkey/desktop"
run_cmd="pdrun github-desktop --no-sandbox"

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="arm64" ;;
armv7*|arm) archtype="arm" ;;
esac


if [[ "$selected_distro" == "ubuntu" ]] || [[ "$selected_distro" == "debian" ]]; then
    cd $working_dir
    download_file "${page_url}/download/release-${version}/GitHubDesktop-linux-${archtype}-${version}.deb"
    distro_run "apt install ./GitHubDesktop-linux-${archtype}-${version}.deb -y"
    check_and_delete "${working_dir}/GitHubDesktop-linux-${archtype}-${version}.deb"
elif [[ "$selected_distro" == "fedora" ]]; then
    cd $working_dir
    download_file "${page_url}/download/release-${version}/GitHubDesktop-linux-${app_arch}-${version}.rpm"
    distro_run "dnf install ./GitHubDesktop-linux-${app_arch}-${version}.rpm -y"
    check_and_delete "${working_dir}/GitHubDesktop-linux-${app_arch}-${version}.rpm"
else
    print_failed "Unsupported distro"
fi

cp ${distro_path}/usr/share/applications/github-desktop.desktop ${PREFIX}/share/applications/ || print_failed "Failed to move menu launcher file"
fix_exec "github-desktop.desktop" "--no-sandbox"