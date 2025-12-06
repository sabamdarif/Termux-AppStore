#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="code"
version=distro_local_version
app_type="distro"
supported_distro="all"
run_cmd="/usr/share/antigravity/antigravity --no-sandbox"

if [[ "$selected_distro" == "debian" ]] || [[ "$selected_distro" == "ubuntu" ]]; then

	distro_run '
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://us-central1-apt.pkg.dev/doc/repo-signing-key.gpg | sudo gpg --dearmor --yes -o /etc/apt/keyrings/antigravity-repo-key.gpg
echo "deb [signed-by=/etc/apt/keyrings/antigravity-repo-key.gpg] https://us-central1-apt.pkg.dev/projects/antigravity-auto-updater-dev/ antigravity-debian main" | sudo tee /etc/apt/sources.list.d/antigravity.list > /dev/null
sudo apt update
sudo apt install antigravity -y
'

elif [[ "$selected_distro" == "fedora" ]]; then
	distro_run '
sudo tee /etc/yum.repos.d/antigravity.repo << EOL
[antigravity-rpm]
name=Antigravity RPM Repository
baseurl=https://us-central1-yum.pkg.dev/projects/antigravity-auto-updater-dev/antigravity-rpm
enabled=1
gpgcheck=0
EOL
sudo dnf makecache
sudo dnf install antigravity -y
'
fi

# Determine which logo file to use
if [ -f "${HOME}/.appstore/logo/Antigravity/logo.png" ]; then
	icon_path="${HOME}/.appstore/logo/Antigravity/logo.png"
elif [ -f "${HOME}/.appstore/logo/Antigravity/logo.svg" ]; then
	icon_path="${HOME}/.appstore/logo/Antigravity/logo.svg"
else
	icon_path="${HOME}/.appstore/logo/Antigravity/logo"
fi

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee ${PREFIX}/share/applications/pd_added/antigravity.desktop >/dev/null
[Desktop Entry]
Name=Antigravity
Comment=Experience liftoff
GenericName=Text Editor
Exec=pdrun ${run_cmd}
Icon=${icon_path}
Type=Application
StartupNotify=false
StartupWMClass=Antigravity
Categories=TextEditor;Development;IDE;
MimeType=application/x-antigravity-workspace;
Actions=new-empty-window;
Keywords=vscode;
DESKTOP_EOF
