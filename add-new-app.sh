#!/bin/bash

CATEGORIES=(
	"Accessories"
	"Development"
	"Games"
	"Graphics"
	"Internet"
	"Multimedia"
	"Office"
	"Productivity"
)

sanitize_folder_name() {
	local name="$1"
	# Convert to lowercase, capitalize first letter, replace spaces with hyphens
	name=$(echo "$name" | tr '[:upper:]' '[:lower:]' | sed 's/^ *\(.\)/\U\1/')
	echo "${name// /-}"
}

get_valid_input() {
	local prompt="$1"
	local valid_options=("${@:2}")

	while true; do
		read -r -p "$prompt" choice
		choice=$(echo "$choice" | tr -d '[:space:]')

		for option in "${valid_options[@]}"; do
			if [ "$choice" = "$option" ]; then
				echo "$choice"
				return 0
			fi
		done

		echo "Invalid choice. Please choose from: ${valid_options[*]}"
	done
}

get_multiple_choices() {
	local prompt="$1"
	local valid_options=("${@:2}")

	while true; do
		read -r -p "$prompt" choices
		IFS=',' read -ra selected <<<"$choices"

		valid=true
		for choice in "${selected[@]}"; do
			choice=$(echo "$choice" | tr -d '[:space:]')
			found=false

			for option in "${valid_options[@]}"; do
				if [ "$choice" = "$option" ]; then
					found=true
					break
				fi
			done

			if [ "$found" = false ]; then
				valid=false
				break
			fi
		done

		if [ "$valid" = true ]; then
			echo "${selected[*]}"
			return 0
		fi

		echo "Invalid choice(s). Please choose from: ${valid_options[*]}"
	done
}

create_install_script() {
	local folder_path="$1"
	local app_type="$2"
	local supported_distro="$3"
	local package_name="$4"
	local run_cmd="$5"
	local supported_arch="$6"
	local is_repo_pkg="$7"
	local download_url="$8"

	cat >"$folder_path/install.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash

supported_arch="$supported_arch"
package_name="$package_name"
run_cmd="$run_cmd"
version="$version"
app_type="$app_type"
EOF

	if [ "$app_type" = "native" ]; then
		cat >>"$folder_path/install.sh" <<'EOF'
progress_phase "prepare" 0 "Preparing to install..."
package_install_and_check "$package_name"
progress_done
EOF
	elif [ "$is_repo_pkg" = "yes" ]; then
		cat >>"$folder_path/install.sh" <<EOF
progress_phase "prepare" 0 "Preparing distro packages..."

# Install based on distro type
case "\$SELECTED_DISTRO" in
    "debian"|"ubuntu")
        pd_package_install_and_check "$package_name"
        ;;
    "fedora")
        pd_package_install_and_check "$package_name"
        ;;
	"arch*")
        pd_package_install_and_check "$package_name"
        ;;
    *)
        echo "Unsupported distribution: \$SELECTED_DISTRO"
        exit 1
        ;;
esac

fix_exec "pd_added/$package_name.desktop" "--no-sandbox"
progress_done
EOF
	else
		# Extract the base URL (everything before /releases/download/)
		local base_url
		base_url="${download_url%/releases/download/*}"

		if [[ "$download_url" =~ \.AppImage$ ]]; then
			# Extract the filename pattern from the download URL
			local filename_pattern
			filename_pattern=$(basename "$download_url")
			# Replace the version and arch in the pattern with variables
			filename_pattern=$(echo "$filename_pattern" | sed "s/$version/\${version}/g" | sed "s/${version#v}/\${version#v}/g" | sed "s/$supported_arch/\${supported_arch}/g")

			cat >>"$folder_path/install.sh" <<EOF
supported_distro="$supported_distro"
page_url="$base_url"
run_cmd="/opt/AppImageLauncher/$package_name/$package_name --no-sandbox"

cd \${TMPDIR}

app_arch=\$(uname -m)
case "\$app_arch" in
    aarch64) archtype="arm64" ;;
    armv7*|arm) archtype="armv7l" ;;
    *) print_failed "Unsupported architectures" ;;
esac

appimage_filename="$filename_pattern"

check_and_delete "\${TMPDIR}/\${appimage_filename} \${TERMUX_PREFIX}/share/applications/pd_added/$package_name.desktop"

progress_phase "download" 0 "Downloading $package_name AppImage..."
download_file "\${page_url}/releases/download/\${version}/\${appimage_filename}"
install_appimage "\${appimage_filename}" "$package_name"

# Determine which logo file to use
if [ -f "\${HOME}/.appstore/logo/$folder_name/logo.png" ]; then
    icon_path="\${HOME}/.appstore/logo/$folder_name/logo.png"
elif [ -f "\${HOME}/.appstore/logo/$folder_name/logo.svg" ]; then
    icon_path="\${HOME}/.appstore/logo/$folder_name/logo.svg"
else
    icon_path="\${HOME}/.appstore/logo/$folder_name/logo"
fi

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee "\${TERMUX_PREFIX}"/share/applications/pd_added/$package_name.desktop >/dev/null
[Desktop Entry]
Name=${package_name^}
Exec=pdrun \${run_cmd}
Terminal=false
Type=Application
Icon=\${icon_path}
StartupWMClass=$package_name
Comment=$package_name
MimeType=x-scheme-handler/$package_name;
Categories=${selected_categories[0]};
DESKTOP_EOF
progress_done
EOF
		elif [[ "$download_url" =~ \.deb$ ]]; then
			# Extract the filename pattern from the download URL
			local filename_pattern
			filename_pattern=$(basename "$download_url")
			# Replace the version and arch in the pattern with variables
			filename_pattern=$(echo "$filename_pattern" | sed "s/$version/\${version}/g" | sed "s/${version#v}/\${version#v}/g" | sed "s/$supported_arch/\${supported_arch}/g")
			cat >>"$folder_path/install.sh" <<EOF
supported_distro="$supported_distro"
page_url="$base_url"
working_dir="\${distro_path}/root"

app_arch=\$(uname -m)
case "\$app_arch" in
    aarch64) archtype="arm64" ;;
    armv7*|arm) archtype="armv7l" ;;
    *) print_failed "Unsupported architectures" ;;
esac

if [[ "\$SELECTED_DISTRO" == "ubuntu" ]] || [[ "\$SELECTED_DISTRO" == "debian" ]]; then
    filename="$filename_pattern"
    temp_download="\$TMPDIR/\${filename}"
    download_file "\$temp_download" "\${page_url}/releases/download/\${version}/\${filename}"
	pd_check_and_delete "/root/\${filename}"
	"\${SELECTED_DISTRO_TYPE}"-distro login "\$SELECTED_DISTRO" -- cp "\$temp_download" "/root/\${filename}"

	pd_update_sys
    distro_run "
apt install /root/\${filename} -y
"
pd_check_and_delete "/root/\${filename}"

elif [[ "\$SELECTED_DISTRO" == "fedora" ]]; then
    filename="$filename_pattern"
    temp_download="\$TMPDIR/\${filename}"
    download_file "\$temp_download" "\${page_url}/releases/download/\${version}/\${filename}"
	pd_check_and_delete "/root/app_installer"
	pd_check_and_delete "/root/\${filename}"
	"\${SELECTED_DISTRO_TYPE}"-distro login "\$SELECTED_DISTRO" -- cp "\$temp_download" "/root/\${filename}"

	pd_package_install_and_check --just "ar atk dbus-libs libnotify libXtst nss alsa-lib pulseaudio-libs libXScrnSaver glibc gtk3 mesa-libgbm libX11-xcb libappindicator-gtk3"

    distro_run "
cd /root
check_and_create_directory 'app_installer'
mv \${filename} app_installer/
cd app_installer
ar x \${filename}
extract 'data.tar.xz'
mv opt/* /opt
cd /root
check_and_delete 'app_installer'
"
else
    print_failed "Unsupported distro"
fi

# Determine which logo file to use
if [ -f "\${HOME}/.appstore/logo/$folder_name/logo.png" ]; then
    icon_path="\${HOME}/.appstore/logo/$folder_name/logo.png"
elif [ -f "\${HOME}/.appstore/logo/$folder_name/logo.svg" ]; then
    icon_path="\${HOME}/.appstore/logo/$folder_name/logo.svg"
else
    icon_path="\${HOME}/.appstore/logo/$folder_name/logo"
fi

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee "\${TERMUX_PREFIX}"/share/applications/pd_added/$package_name.desktop >/dev/null
[Desktop Entry]
Name=${package_name^}
Exec=pdrun \${run_cmd}
Terminal=false
Type=Application
Icon=\${icon_path}
StartupWMClass=$package_name
Comment=$package_name
MimeType=x-scheme-handler/$package_name;
Categories=${selected_categories[0]};
DESKTOP_EOF
progress_done
EOF
		else
			# For tar/archive installations
			# Extract the filename pattern from the download URL
			local filename_pattern
			filename_pattern=$(basename "$download_url")
			# Replace the version and arch in the pattern with variables
			filename_pattern=$(echo "$filename_pattern" | sed "s/$version/\${version}/g" | sed "s/${version#v}/\${version#v}/g" | sed "s/$supported_arch/\${supported_arch}/g")

			cat >>"$folder_path/install.sh" <<EOF
supported_distro="$supported_distro"
page_url="$base_url"
working_dir="\${distro_path}/opt"

# Check if a distro is selected
if [ -z "\$SELECTED_DISTRO" ]; then
    print_failed "Error: No distro selected"
    exit 1
fi

app_arch=\$(uname -m)
case "\$app_arch" in
    aarch64) archtype="arm64" ;;
    armv7*|arm|armv8l) archtype="armhf" ;;
    *) print_failed "Unsupported architectures" ;;
esac

filename="$filename_pattern"
temp_download="\$TMPDIR/\${filename}"
download_file "\$temp_download" "\${page_url}/releases/download/\${version}/\${filename}"

pd_check_and_delete "/opt/$package_name"
pd_check_and_create_directory "/opt/$package_name"

"\${SELECTED_DISTRO_TYPE}"-distro login "\$SELECTED_DISTRO" -- cp "\$temp_download" "\${working_dir}/$package_name/\${filename}"


distro_run "
cd /opt/$package_name
extract '\${filename}'
check_and_delete '\${filename}'
"

# Determine which logo file to use
if [ -f "\${HOME}/.appstore/logo/$folder_name/logo.png" ]; then
    icon_path="\${HOME}/.appstore/logo/$folder_name/logo.png"
elif [ -f "\${HOME}/.appstore/logo/$folder_name/logo.svg" ]; then
    icon_path="\${HOME}/.appstore/logo/$folder_name/logo.svg"
else
    icon_path="\${HOME}/.appstore/logo/$folder_name/logo"
fi

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee "\${TERMUX_PREFIX}"/share/applications/pd_added/$package_name.desktop >/dev/null
[Desktop Entry]
Name=${package_name^}
Exec=pdrun \${run_cmd}
Terminal=false
Type=Application
Icon=\${icon_path}
StartupWMClass=$package_name
Comment=$package_name
MimeType=x-scheme-handler/$package_name;
Categories=${selected_categories[0]};
DESKTOP_EOF
progress_done
EOF
		fi
	fi

	chmod 755 "$folder_path/install.sh"
}

create_uninstall_script() {
	local folder_path="$1"
	local package_name="$2"
	local is_repo_pkg="$3"
	local download_url="$4"

	if [ "$app_type" = "native" ]; then
		cat >"$folder_path/uninstall.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing $package_name..."
package_remove_and_check "$package_name"
progress_done
EOF
	elif [ "$is_repo_pkg" = "yes" ]; then
		cat >"$folder_path/uninstall.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing $package_name..."
case "\$SELECTED_DISTRO" in
    "debian"|"ubuntu")
        \$SELECTED_DISTRO remove $package_name -y
        ;;
    "fedora")
        \$SELECTED_DISTRO remove $package_name -y
        ;;
    *)
        echo "Unsupported distribution: \$SELECTED_DISTRO"
        exit 1
        ;;
esac

check_and_delete "\$TERMUX_PREFIX/share/applications/pd_added/$package_name.desktop"
progress_done
EOF
	else
		if [[ "$download_url" =~ \.AppImage$ ]]; then
			# For AppImage uninstallation
			cat >"$folder_path/uninstall.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing $package_name AppImage..."
check_and_delete "\${distro_path}/opt/AppImageLauncher/$package_name"
check_and_delete "\${distro_path}/usr/share/icons/hicolor/*/apps/$package_name.png"
check_and_delete "\${TERMUX_PREFIX}/share/applications/pd_added/$package_name.desktop"
progress_done
EOF
		elif [[ "$download_url" =~ \.deb$ ]]; then
			cat >"$folder_path/uninstall.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash

if [[ "\$SELECTED_DISTRO" == "ubuntu" ]] || [[ "\$SELECTED_DISTRO" == "debian" ]]; then
    distro_run "
apt remove $package_name -y
"
elif [[ "\$SELECTED_DISTRO" == "fedora" ]]; then
    pd_check_and_delete "/opt/$package_name"
else
    print_failed "Unsupported distro"
fi

check_and_delete "\${TERMUX_PREFIX}/share/applications/pd_added/$package_name.desktop"
progress_done
EOF
		else
			cat >"$folder_path/uninstall.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash

progress_phase "cleanup" 0 "Removing $package_name..."
pd_check_and_delete '/opt/$package_name'

check_and_delete "\${TERMUX_PREFIXFIX}/share/applications/pd_added/$package_name.desktop"
progress_done
EOF
		fi
	fi

	chmod 755 "$folder_path/uninstall.sh"
}

main() {
	# Get app information
	read -r -p "Enter app name: " app_name
	folder_name=$(sanitize_folder_name "$app_name")

	# Get supported architectures
	supported_archs=$(get_multiple_choices "Enter supported architectures (comma-separated: aarch64,arm): " "aarch64" "arm")

	app_type=$(get_valid_input "Enter app type (native/distro): " "native" "distro")

	supported_distro="all"
	is_repo_pkg="yes"
	download_url=""
	version=""

	if [ "$app_type" = "distro" ]; then
		supported_distro=$(get_valid_input "Enter supported distro (debian/ubuntu/fedora/all): " "debian" "ubuntu" "fedora" "all")

		read -r -p "Is it available in the distro's repository? (yes/no): " is_repo_pkg
		is_repo_pkg=$(echo "$is_repo_pkg" | tr '[:upper:]' '[:lower:]')

		if [ "$is_repo_pkg" != "yes" ] && [ "$is_repo_pkg" != "y" ]; then
			is_repo_pkg="no"
			read -r -p "Enter the download URL for the file: " download_url
			# Extract version from GitHub URL
			if [[ $download_url =~ /releases/download/(v[0-9]+\.[0-9]+\.[0-9]+)/ ]]; then
				version="${BASH_REMATCH[1]}"
				echo "Detected version: $version"
			else
				read -r -p "Could not detect version from URL. Please enter version manually: " version
			fi
		else
			is_repo_pkg="yes"
			read -r -p "Enter version (press Enter for default): " version
			version=${version:-${app_type}_local_version}
		fi
	else
		read -r -p "Enter version (press Enter for default): " version
		version=${version:-termux_local_version}
	fi

	# Get package details
	read -r -p "Enter package name: " package_name

	if [ "$app_type" = "distro" ] && [ "$is_repo_pkg" = "no" ] && [[ ! "$download_url" =~ \.AppImage$ ]] && [[ ! "$download_url" =~ \.deb$ ]]; then
		# For tar archives, set default run command
		run_cmd="/opt/$package_name/$package_name --no-sandbox"
	else
		read -r -p "Enter run command: " run_cmd
	fi

	# Get description
	echo -e "\nEnter app description (press Ctrl+D twice to finish):"
	description=$(cat)

	# Select categories
	echo -e "\nAvailable categories:"
	for i in "${!CATEGORIES[@]}"; do
		echo "$((i + 1)). ${CATEGORIES[i]}"
	done

	selected_categories=()
	while true; do
		read -r -p $'\nSelect category number (press Enter when done): ' choice

		[ -z "$choice" ] && break

		if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#CATEGORIES[@]}" ]; then
			category="${CATEGORIES[$((choice - 1))]}"
			# Check if category already exists
			category_exists=false
			for existing_cat in "${selected_categories[@]}"; do
				if [ "$existing_cat" = "$category" ]; then
					category_exists=true
					break
				fi
			done

			if [ "$category_exists" = false ]; then
				selected_categories+=("$category")
				echo "Added: $category"
			fi
		else
			echo "Invalid category number"
		fi
	done

	if [ ${#selected_categories[@]} -eq 0 ]; then
		echo "At least one category must be selected"
		return 1
	fi

	# Create app directory and files
	apps_dir="apps"
	app_dir="$apps_dir/$folder_name"

	if [ -d "$app_dir" ]; then
		echo "Error: App directory '$folder_name' already exists"
		return 1
	fi

	mkdir -p "$app_dir"

	# Create description.txt file
	echo "$description" >"$app_dir/description.txt"

	# Create category file
	(
		IFS=,
		echo "${selected_categories[*]}"
	) >"$app_dir/category.txt"

	# Create install and uninstall scripts
	local archs_csv
	archs_csv=$(echo "$supported_archs" | tr ' ' ',')
	create_install_script "$app_dir" "$app_type" "$supported_distro" "$package_name" "$run_cmd" "$archs_csv" "$is_repo_pkg" "$download_url"
	create_uninstall_script "$app_dir" "$package_name" "$is_repo_pkg" "$download_url"

	# Handle logo
	while true; do
		read -r -p $'\nEnter path to logo (PNG or SVG): ' logo_path

		# Remove quotes if present
		logo_path="${logo_path//[\'\"]/}"

		if [ -f "$logo_path" ]; then
			# Check file extension
			if [[ "$logo_path" =~ \.png$ ]]; then
				cp "$logo_path" "$app_dir/logo.png"
				echo "PNG logo copied successfully"
				break
			elif [[ "$logo_path" =~ \.svg$ ]]; then
				cp "$logo_path" "$app_dir/logo.svg"
				echo "SVG logo copied successfully"
				break
			else
				echo "Invalid file format. Please provide a PNG or SVG file."
			fi
		else
			echo "Invalid path or file does not exist"
		fi
	done

	echo -e "\nApp '$app_name' created successfully in $app_dir"
}

main "$@"
