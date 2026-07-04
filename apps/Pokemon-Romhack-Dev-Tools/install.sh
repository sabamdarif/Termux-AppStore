#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm64"
version="1.0.0"
app_type="distro"
supported_distro="debian,ubuntu,arch,archlinux"
package_name="gba-dev"

progress_phase "prepare" 0 "Preparing Pokemon ROM hack tools..."

if [ -z "$SELECTED_DISTRO" ]; then
	print_failed "Error: No distro selected"
	exit 1
fi

case "$SELECTED_DISTRO" in
"debian" | "ubuntu" | "arch" | "archlinux") ;;
*)
	print_failed "Automated devkitPro setup is not supported for $SELECTED_DISTRO"
	print_msg "Use a Debian, Ubuntu, or Arch container for this bundle."
	exit 1
	;;
esac

progress_phase "install" 0 "Installing Termux build dependencies..."
package_install_and_check "make nasm clang perl xdelta3 python git"

progress_phase "install" 40 "Installing Python ROM hacking libraries..."
if ! python -m pip install --upgrade Pillow PyYAML ndspy colorama; then
	print_warn "Regular pip install failed; retrying with --break-system-packages..."
	python -m pip install --break-system-packages --upgrade Pillow PyYAML ndspy colorama || exit 1
fi

progress_phase "configure" 0 "Installing distro prerequisites..."
case "$SELECTED_DISTRO" in
"debian" | "ubuntu")
	pd_package_install_and_check --just "wget ca-certificates build-essential libpng-dev"
	romhack_setup_content=$(
		cat <<'ROMHACK_SETUP'
set -e
cd /root
rm -f install-devkitpro-pacman
wget -q --show-progress https://apt.devkitpro.org/install-devkitpro-pacman
chmod +x install-devkitpro-pacman
printf 'Y\n' | bash install-devkitpro-pacman

if command -v dkp-pacman >/dev/null 2>&1; then
	DKP_PACMAN=dkp-pacman
elif [ -x /opt/devkitpro/pacman/bin/dkp-pacman ]; then
	DKP_PACMAN=/opt/devkitpro/pacman/bin/dkp-pacman
else
	echo "Unable to locate dkp-pacman after devkitPro setup"
	exit 1
fi

"$DKP_PACMAN" -S --noconfirm gba-dev nds-dev
rm -f install-devkitpro-pacman
ROMHACK_SETUP
	)
	distro_run "$romhack_setup_content"
	;;
"arch" | "archlinux")
	romhack_setup_content=$(
		cat <<'ROMHACK_SETUP'
set -e
rm -f /var/lib/pacman/db.lck
pacman -Sy --noconfirm
pacman -S --noconfirm wget ca-certificates base-devel libpng

pacman-key --recv BC26F752D25B92CE272E0F44F7FD5492264BB9D0
pacman-key --lsign-key BC26F752D25B92CE272E0F44F7FD5492264BB9D0

if ! grep -q '^\[dkp-libs\]' /etc/pacman.conf; then
	cat >>/etc/pacman.conf <<'PACMAN_REPOS'

[dkp-libs]
Server = https://pkg.devkitpro.org/packages
[dkp-linux]
Server = https://pkg.devkitpro.org/packages/linux/$arch/
PACMAN_REPOS
fi

pacman -Syu --noconfirm
pacman -S --noconfirm gba-dev nds-dev
ROMHACK_SETUP
	)
	distro_run "$romhack_setup_content"
	;;
esac

progress_phase "configure" 70 "Creating devkitPro shell launchers..."
launcher_setup_content=$(
	cat <<'LAUNCHER_SETUP'
set -e
cat >/etc/profile.d/pokemon-romhack-dev.sh <<'PROFILE_EOF'
export DEVKITPRO=/opt/devkitpro
export DEVKITARM=${DEVKITPRO}/devkitARM
export DEVKITPPC=${DEVKITPRO}/devkitPPC
export PATH=${DEVKITPRO}/tools/bin:${DEVKITARM}/bin:${PATH}
PROFILE_EOF

cat >/usr/local/bin/pokemon-romhack-dev-shell <<'SHELL_EOF'
#!/bin/sh
if [ -f /etc/profile.d/pokemon-romhack-dev.sh ]; then
	. /etc/profile.d/pokemon-romhack-dev.sh
fi
cd "${HOME:-/root}"
exec "${SHELL:-/bin/bash}" -l
SHELL_EOF

chmod +x /usr/local/bin/pokemon-romhack-dev-shell
LAUNCHER_SETUP
)
distro_run "$launcher_setup_content"

cat >"${TERMUX_PREFIX}/bin/pokemon-romhack-dev-shell" <<'TERMUX_LAUNCHER'
#!/data/data/com.termux/files/usr/bin/bash

TERMUX_PREFIX=${PREFIX:-/data/data/com.termux/files/usr}
CONFIG_FILE="$TERMUX_PREFIX/etc/termux-desktop/configuration.conf"

if [ ! -f "$CONFIG_FILE" ]; then
	echo "Termux Desktop configuration not found: $CONFIG_FILE" >&2
	exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"

selected_distro_type="${selected_distro_type:-proot}"

if [ -z "${selected_distro:-}" ]; then
	echo "No selected distro configured." >&2
	exit 1
fi

exec "${selected_distro_type}-distro" login "$selected_distro" --shared-tmp -- /usr/local/bin/pokemon-romhack-dev-shell
TERMUX_LAUNCHER
chmod +x "${TERMUX_PREFIX}/bin/pokemon-romhack-dev-shell"

check_and_create_directory "${TERMUX_PREFIX}/share/applications/pd_added"
cat >"${TERMUX_PREFIX}/share/applications/pd_added/pokemon-romhack-dev-shell.desktop" <<EOF
[Desktop Entry]
Name=Pokemon ROM Hack Dev Shell
Exec=env TERM=xterm-256color pokemon-romhack-dev-shell
Terminal=true
Type=Application
Icon=${HOME}/.appstore/logo/Pokemon-Romhack-Dev-Tools/logo.png
Comment=devkitPro GBA/NDS toolchain shell
Categories=Development;Game;
EOF

progress_done
