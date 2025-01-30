#!/bin/bash

check_and_delete "${distro_path}/opt/AppImageLauncher/Obsidian"
check_and_delete "${distro_path}/usr/share/icons/hicolor/*/apps/obsidian.png"
check_and_delete "${PREFIX}/share/applications/obsidian.desktop"
