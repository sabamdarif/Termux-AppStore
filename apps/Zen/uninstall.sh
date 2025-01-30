#!/data/data/com.termux/files/usr/bin/bash

check_and_delete "${distro_path}/opt/zen-browser ${PREFIX}/usr/share/applications/zen-browser.desktop"

for i in 16x16 32x32 48x48 64x64 128x128; do
  check_and_delete "${PREFIX}/usr/share/icons/hicolor/$i/apps/zen-browser.png"
done
