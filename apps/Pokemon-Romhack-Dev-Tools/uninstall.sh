#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing Pokemon ROM hack tool launchers..."

check_and_delete "${TERMUX_PREFIX}/bin/pokemon-romhack-dev-shell"
check_and_delete "${TERMUX_PREFIX}/share/applications/pd_added/pokemon-romhack-dev-shell.desktop"

progress_phase "cleanup" 20 "Removing Termux ROM hack helper packages..."
package_remove_and_check "xdelta3"

progress_phase "cleanup" 30 "Removing Python ROM hack libraries..."
if command -v python >/dev/null 2>&1; then
	romhack_python_packages="Pillow PyYAML ndspy colorama"
	if ! python -m pip uninstall -y $romhack_python_packages; then
		print_warn "Regular pip uninstall failed; retrying with --break-system-packages..."
		python -m pip uninstall --break-system-packages -y $romhack_python_packages || true
	fi
fi

if [ -n "${SELECTED_DISTRO:-}" ]; then
	progress_phase "cleanup" 40 "Removing distro ROM hack packages..."
	case "$SELECTED_DISTRO" in
	"debian" | "ubuntu")
		romhack_cleanup_content=$(
			cat <<'ROMHACK_CLEANUP'
if command -v dkp-pacman >/dev/null 2>&1; then
	DKP_PACMAN=dkp-pacman
elif [ -x /opt/devkitpro/pacman/bin/dkp-pacman ]; then
	DKP_PACMAN=/opt/devkitpro/pacman/bin/dkp-pacman
else
	DKP_PACMAN=
fi

if [ -n "$DKP_PACMAN" ]; then
	"$DKP_PACMAN" -Rns --noconfirm gba-dev nds-dev || true
fi

rm -f /usr/local/bin/pokemon-romhack-dev-shell
rm -f /etc/profile.d/pokemon-romhack-dev.sh
ROMHACK_CLEANUP
		)
		distro_run "$romhack_cleanup_content"
		;;
	"arch" | "archlinux")
		romhack_cleanup_content=$(
			cat <<'ROMHACK_CLEANUP'
pacman -Rns --noconfirm gba-dev nds-dev || true
rm -f /usr/local/bin/pokemon-romhack-dev-shell
rm -f /etc/profile.d/pokemon-romhack-dev.sh
ROMHACK_CLEANUP
		)
		distro_run "$romhack_cleanup_content"
		;;
	*)
		print_warn "Skipping distro package removal for unsupported distro: $SELECTED_DISTRO"
		;;
	esac
fi

progress_done
