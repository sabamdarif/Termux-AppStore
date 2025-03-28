#!/bin/bash

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
if [[ "$ID" == "ubuntu" || "$ID_LIKE" == *"ubuntu"* ]]; then
    echo "Running on Ubuntu, proceeding with installation..."
else
    echo "This application is only supported on Ubuntu!"
    exit 1
fi

# OrcaSlicer Installation, ICO Conversion, and Desktop Shortcut Script

# --- Step 1: Download and Install OrcaSlicer ---

DEB_FILE="OrcaSlicer_UbuntuLinux_V2.3.0-devARM64.deb"
DOWNLOAD_URL="https://github.com/CodeMasterCody3D/OrcaSlicer/releases/download/arm64/$DEB_FILE"

echo "Downloading OrcaSlicer deb file..."
pdrun wget -O "$HOME/$DEB_FILE" "$DOWNLOAD_URL"

echo "Installing OrcaSlicer..."
pdrun sudo dpkg -i "$HOME/$DEB_FILE"

echo "Fixing missing dependencies..."
pdrun sudo apt-get install -f -y

echo "OrcaSlicer installation completed!"

# --- Step 2: Download the ICO file ---
ICO_FILE_URL="https://github.com/CodeMasterCody3D/OrcaSlicer/releases/download/arm64/OrcaSlicer.ico"
ICO_FILE_PATH="$HOME/OrcaSlicer.ico"  # Save the ICO file in the home directory

echo "Downloading ICO file..."
wget -O "$ICO_FILE_PATH" "$ICO_FILE_URL"

# --- Step 3: Convert ICO to PNG ---
# This uses the tested one-liner to take the first image from the ICO file,
# resize it to 256x256, and output a PNG.
PNG_FILE_PATH="$HOME/OrcaSlicer.png"

# Check if the ICO file exists
if [ ! -f "$ICO_FILE_PATH" ]; then
  echo "Error: ICO file not found at $ICO_FILE_PATH"
  exit 1
fi

echo "Installing ImageMagick (if not already installed)..."
pkg install -y imagemagick

echo "Converting ICO to PNG..."
convert "$ICO_FILE_PATH[5]" -resize 256x256 "$PNG_FILE_PATH"
echo "PNG conversion completed. Output file: $PNG_FILE_PATH"

# --- Step 4: Copy the PNG Icon to the Icons Directory ---
ICON_DIR="/data/data/com.termux/files/usr/share/icons/hicolor/256x256/apps/"

echo "Ensuring icon directory exists at $ICON_DIR..."
mkdir -p "$ICON_DIR"

echo "Copying PNG icon to $ICON_DIR..."
cp "$PNG_FILE_PATH" "$ICON_DIR"

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
Exec=pdrun orca-slicer
Icon=$ICON_DIR/OrcaSlicer.png
Terminal=false
Categories=Graphics;3DPrinting;
EOF

chmod +x "$SHORTCUT_FILE"

echo "Desktop shortcut created successfully at $SHORTCUT_FILE"

echo "OrcaSlicer installation completed!"
