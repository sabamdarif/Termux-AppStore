#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="code"
version=distro_local_version
app_type="distro"
supported_distro="all"
# working_dir="${distro_path}"
package_name="code"
run_cmd="/usr/share/code/code --no-sandbox"

if [[ "$selected_distro" == "debian" ]] || [[ "$selected_distro" == "ubuntu" ]]; then

    distro_run '
# Update package lists without manual confirmation
sudo apt update -y -o Dpkg::Options::="--force-confnew"

# Install necessary packages without prompts
sudo apt-get install -y wget gpg apt-transport-https

# Download and store the Microsoft GPG key
wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor | sudo tee /etc/apt/keyrings/packages.microsoft.gpg > /dev/null

# Set correct permissions on the key
sudo install -D -o root -g root -m 644 /etc/apt/keyrings/packages.microsoft.gpg /etc/apt/keyrings/packages.microsoft.gpg

# Add the VS Code repository non-interactively
echo "deb [arch=amd64,arm64,armhf signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main" | sudo tee /etc/apt/sources.list.d/vscode.list > /dev/null

# Final update of package lists
sudo apt-get update -y
'
    $selected_distro install code -y
elif [[ "$selected_distro" == "fedora" ]]; then
    distro_run '
# Import Microsoft GPG key
sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc

# Add the VS Code repository without user interaction
echo -e "[code]\nname=Visual Studio Code\nbaseurl=https://packages.microsoft.com/yumrepos/vscode\nenabled=1\ngpgcheck=1\ngpgkey=https://packages.microsoft.com/keys/microsoft.asc" | sudo tee /etc/yum.repos.d/vscode.repo > /dev/null

# Update the package list
sudo dnf check-update -y
'
    $selected_distro install code -y
fi
sed -i 's|^Exec=.*|Exec=pdrun /usr/share/code/code --no-sandbox|g' "/data/data/com.termux/files/usr/share/applications/pd_added/code.desktop"
