#!/data/data/com.termux/files/usr/bin/bash

supported_arch="arm64"
version="V2.3.0"
app_type="distro"
supported_distro="ubuntu,debian"
working_dir="${distro_path}/root"
page_url="https://github.com/CodeMasterCody3D/OrcaSlicer/releases"
run_cmd="orca-slicer"

echo "Downloading install script..."
echo "Preparing installation..."

# Get OS details inside PRoot
OS_INFO=$(pdrun cat /etc/os-release)

# Extract OS ID and ID_LIKE
ID=$(echo "$OS_INFO" | grep '^ID=' | cut -d= -f2 | tr -d '"')
ID_LIKE=$(echo "$OS_INFO" | grep '^ID_LIKE=' | cut -d= -f2 | tr -d '"')

echo "Detected OS: $ID"
echo "ID_LIKE: $ID_LIKE"

# Check if running on Ubuntu
if [[ "$selected_distro" == "ubuntu" || "$selected_distro" == "debian"* ]]; then
    cd $working_dir
    filename="OrcaSlicer_UbuntuLinux_${version}-dev${supported_arch}.deb"
    # --- Step 1: Download and Install OrcaSlicer ---
    echo "Downloading OrcaSlicer deb file..."
    download_file "${page_url}/releases/download/${supported_arch}/${filename}"
    distro_run "sudo dpkg -i ${filename}"
    distro_run "sudo apt-get install -f -y"
    check_and_delete "${working_dir}/${filename}"
else
    echo "This application is only supported on Ubuntu!"
    exit 1
fi

# --- Step 4: Copy the PNG Icon to the Icons Directory ---
# ICON_DIR="/data/data/com.termux/files/usr/share/icons/hicolor/256x256/apps/"

# echo "Ensuring icon directory exists at $ICON_DIR..."
# mkdir -p "$ICON_DIR"

# echo "Copying PNG icon to $ICON_DIR..."
# cp "$PNG_FILE_PATH" "$ICON_DIR"

# --- Step 5: Create the Desktop Shortcut ---
DESKTOP_DIR="$HOME/Desktop"
SHORTCUT_FILE="$DESKTOP_DIR/OrcaSlicer.desktop"

echo "Ensuring Desktop directory exists..."
mkdir -p "$DESKTOP_DIR"

echo "Creating desktop shortcut for OrcaSlicer..."
cat <<EOF > "$SHORTCUT_FILE"
[Desktop Entry]
Version=1.0
Type=Application
Name=OrcaSlicer
Exec=pdrun ${run_cmd}
Icon=${HOME}/.appstore/logo/OrcaSlicer/logo.png
Terminal=false
Categories=Graphics;3DPrinting;
EOF

chmod +x "$SHORTCUT_FILE"
cp "$SHORTCUT_FILE" ${PREFIX}/share/applications/pd_added/
echo "Desktop shortcut created successfully at $SHORTCUT_FILE"
