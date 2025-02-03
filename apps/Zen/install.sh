#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
version=1.7.4b
app_type="distro"
supported_distro="all"
working_dir="${distro_path}/opt"
page_url="https://github.com/zen-browser/desktop"
run_cmd="zen-browser"

# chown -R $(whoami):$(whoami) ${distro_path}
cd $working_dir
check_and_delete "zen zen-browser zen-browser-arm64-copr"
echo "$(pwd)"
download_file "${page_url}/releases/download/${version}/zen.linux-${supported_arch}.tar.bz2"
tar -xvjf zen.linux-${supported_arch}.tar.bz2
check_and_delete "zen.linux-${supported_arch}.tar.bz2"
mv zen zen-browser
git clone --depth 1 https://github.com/ArchitektApx/zen-browser-arm64-copr || exit 1
#fix app_id to get taskbar icon working on wayland
sed -i "s+exec zen-browser/zen-bin+exec zen-browser/zen-bin --class zen-browser --name zen-browser+g" zen-browser-arm64-copr/zen-browser || print_failed "failed to edit launcher file"

mv -f zen-browser-arm64-copr/zen-browser ${distro_path}/usr/bin/zen-browser || print_failed "Failed to move zen-browser command"
chmod +x ${distro_path}/usr/bin/zen-browser

#copy menu launcher
mv -f zen-browser-arm64-copr/zen-browser.desktop ${PREFIX}/share/applications/ || print_failed "Failed to move menu launcher file"
fix_exec "zen-browser.desktop"
#disables update notifications
check_and_create_directory "zen-browser/distribution"
mv -f zen-browser-arm64-copr/policies.json $working_dir/zen-browser/distribution || print_failed "Failed to move policies.json file"
#no need for the git repo anymore
check_and_delete "zen-browser-arm64-copr"

#copy icons
for i in 16x16 32x32 48x48 64x64 128x128; do
  check_and_create_directory "${PREFIX}/share/icons/hicolor/$i/apps/"
  cp $working_dir/zen-browser/browser/chrome/icons/default/default${i/x*}.png ${distro_path}/usr/share/icons/hicolor/$i/apps/zen-browser.png || print_failed "Failed to copy $i icon"
done
