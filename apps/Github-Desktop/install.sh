#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
version="release-3.4.13-linux1"
final_version="${version#release-}"
app_type="distro"
supported_distro="all"
working_dir="${distro_path}/root"
page_url="https://github.com/shiftkey/desktop"
run_cmd="github-desktop --no-sandbox"

app_arch=$(uname -m)
case "$app_arch" in
aarch64) archtype="arm64" ;;
armv7*|arm) archtype="armv7l" ;;
*) print_failed "Unsupported architectures" ;;
esac


if [[ "$selected_distro" == "ubuntu" ]] || [[ "$selected_distro" == "debian" ]]; then
    cd $working_dir
    filename="GitHubDesktop-linux-${archtype}-${final_version}.deb"
    download_file "${page_url}/releases/download/${version}/${filename}"
    distro_run "apt install ./${filename} -y"
    check_and_delete "${working_dir}/${filename}"
elif [[ "$selected_distro" == "fedora" ]]; then
    cd $working_dir
    if [[ "$archtype" == "armv7l" ]]; then
    filename="GitHubDesktop-linux-${archtype}-${final_version}.rpm"
    else
    filename="GitHubDesktop-linux-${app_arch}-${final_version}.rpm"
    fi
    download_file "${page_url}/releases/download/${version}/${filename}"
    distro_run "dnf install ./${filename} -y"
    check_and_delete "${working_dir}/${filename}"
else
    print_failed "Unsupported distro"
fi

cp ${distro_path}/usr/share/applications/github-desktop.desktop ${PREFIX}/share/applications/pd_added || print_failed "Failed to move menu launcher file"
fix_exec "pd_added/github-desktop.desktop" "--no-sandbox"