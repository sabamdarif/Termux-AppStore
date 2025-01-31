#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
# version=2.34.1
app_type="distro"
supported_distro="all"
# working_dir=""
run_cmd="libreoffice"

# Check if a distro is selected
if [ -z "$selected_distro" ]; then
    echo "Error: No distro selected"
    exit 1
fi

# Install based on distro type
case "$selected_distro" in
    "debian"|"ubuntu")
        $selected_distro update
        $selected_distro install libreoffice -y
        ;;
    "fedora")
        $selected_distro install libreoffice -y
        ;;
    *)
        echo "Unsupported distribution: $selected_distro"
        exit 1
        ;;
esac

# Check if installation was successful
if [ $? -eq 0 ]; then
    echo "LibreOffice installed successfully"
    exit 0
else
    echo "LibreOffice installation failed"
    exit 1
fi