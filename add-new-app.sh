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
        read -p "$prompt" choice
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
        read -p "$prompt" choices
        IFS=',' read -ra selected <<< "$choices"
        
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
    
    cat > "$folder_path/install.sh" << EOF
#!/data/data/com.termux/files/usr/bin/bash

supported_arch="$supported_arch"
package_name="$package_name"
run_cmd="$run_cmd"
version="$version"
app_type="$app_type"
EOF
    
    if [ "$app_type" = "native" ]; then
        cat >> "$folder_path/install.sh" << 'EOF'
package_install_and_check "$package_name"
EOF
    elif [ "$is_repo_pkg" = "yes" ]; then
        cat >> "$folder_path/install.sh" << EOF
supported_distro="$supported_distro"

# Check if a distro is selected
if [ -z "\$selected_distro" ]; then
    print_failed "Error: No distro selected"
    exit 1
fi

# Install based on distro type
case "\$selected_distro" in
    "debian"|"ubuntu")
        \$selected_distro update -y
        \$selected_distro install $package_name -y
        ;;
    "fedora")
        \$selected_distro update -y
        \$selected_distro install $package_name -y
        ;;
    *)
        echo "Unsupported distribution: \$selected_distro"
        exit 1
        ;;
esac

fix_exec "pd_added/$package_name.desktop" "--no-sandbox"
EOF
    else
        # Extract the base URL (everything before /releases/download/)
        local base_url=$(echo "$download_url" | sed 's|\(.*\)/releases/download/.*|\1|')
        
        if [[ "$download_url" =~ \.AppImage$ ]]; then
            # Extract the filename pattern from the download URL
            local filename_pattern=$(basename "$download_url")
            # Replace the version and arch in the pattern with variables
            filename_pattern=$(echo "$filename_pattern" | sed "s/$version/\${version}/g" | sed "s/${version#v}/\${version#v}/g" | sed "s/$supported_arch/\${supported_arch}/g")
            
            cat >> "$folder_path/install.sh" << EOF
supported_distro="$supported_distro"
page_url="$base_url"
run_cmd="/opt/AppImageLauncher/$package_name/$package_name --no-sandbox"

cd \${TMPDIR}

app_arch=\$(uname -m)
case " \$app_arch" in
aarch64) archtype="arm64" ;;
armv7*|arm) archtype="armv7l" ;;
esac

appimage_filename="$filename_pattern"

check_and_delete "\${TMPDIR}/\${appimage_filename} \${PREFIX}/share/applications/pd_added/$package_name.desktop"

print_success "Downloading $package_name AppImage..."
download_file "\${page_url}/releases/download/\${version}/\$appimage_filename"
install_appimage "\$appimage_filename" "$package_name"

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee \${PREFIX}/share/applications/pd_added/$package_name.desktop >/dev/null
[Desktop Entry]
Name=${package_name^}
Exec=pdrun "\${run_cmd}"
Terminal=false
Type=Application
Icon=\${HOME}/.appstore/logo/$folder_name/logo.png
StartupWMClass=$package_name
Comment=$package_name
MimeType=x-scheme-handler/$package_name;
Categories=${selected_categories[0]};
DESKTOP_EOF
EOF
        elif [[ "$download_url" =~ \.deb$ ]]; then
        # Extract the filename pattern from the download URL
        local filename_pattern=$(basename "$download_url")
        # Replace the version and arch in the pattern with variables
        filename_pattern=$(echo "$filename_pattern" | sed "s/$version/\${version}/g" | sed "s/${version#v}/\${version#v}/g" | sed "s/$supported_arch/\${supported_arch}/g")
        cat >> "$folder_path/install.sh" << EOF
supported_distro="$supported_distro"
page_url="$base_url"
working_dir="\${distro_path}/root"

app_arch=\$(uname -m)
case " \$app_arch" in
aarch64) archtype="arm64" ;;
armv7*|arm) archtype="armv7l" ;;
esac

if [[ "\$selected_distro" == "ubuntu" ]] || [[ "\$selected_distro" == "debian" ]]; then
cd \$working_dir
filename="${filename_pattern}"
distro_run "
check_and_delete "/root/\${filename}"
"
download_file "${page_url}/releases/download/${version}/${filename}"
distro_run "
sudo apt install ./\${filename} -y
check_and_delete "/root/\${filename}"
"
elif [[ "\$selected_distro" == "fedora" ]]; then
cd \$working_dir
filename="${filename_pattern}"
distro_run "
check_and_delete "/root/\${filename}"
"
download_file "\${page_url}/releases/download/\${version}/\${filename}"
distro_run "
cd /root
check_and_delete "app_installer"
check_and_create_directory "app_installer"
mv \${filename} app_installer/
cd app_installer
sudo dnf install -y ar atk dbus-libs libnotify libXtst nss alsa-lib pulseaudio-libs libXScrnSaver glibc gtk3 mesa-libgbm libX11-xcb libappindicator-gtk3
ar x \${filename}
extract "data.tar.xz"
mv opt/* /opt
cd /root
check_and_delete "app_installer"
"
else
    print_failed "Unsupported distro"
fi

print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee \${PREFIX}/share/applications/pd_added/$package_name.desktop >/dev/null
[Desktop Entry]
Name=${package_name^}
Exec=pdrun "\${run_cmd}"
Terminal=false
Type=Application
Icon=\${HOME}/.appstore/logo/$folder_name/logo.png
StartupWMClass=$package_name
Comment=$package_name
MimeType=x-scheme-handler/$package_name;
Categories=${selected_categories[0]};
DESKTOP_EOF
EOF
        else
            # For tar/archive installations
            # Extract the filename pattern from the download URL
            local filename_pattern=$(basename "$download_url")
            # Replace the version and arch in the pattern with variables
            filename_pattern=$(echo "$filename_pattern" | sed "s/$version/\${version}/g" | sed "s/${version#v}/\${version#v}/g" | sed "s/$supported_arch/\${supported_arch}/g")

            cat >> "$folder_path/install.sh" << EOF
page_url="$base_url"
working_dir="\${distro_path}/opt"
supported_distro="$supported_distro"

# Check if a distro is selected
if [ -z "\$selected_distro" ]; then
    print_failed "Error: No distro selected"
    exit 1
fi

distro_run "
check_and_delete '/opt/${package_name}'
check_and_create_directory '/opt/${package_name}'
"
cd \$working_dir/$package_name
echo "\$(pwd)"
download_file "\${page_url}/releases/download/\${version}/${filename_pattern}"
distro_run "
cd /opt/$package_name
echo "\$(pwd)"
extract "${filename_pattern}"
check_and_delete "${filename_pattern}"
"
print_success "Creating desktop entry..."
cat <<DESKTOP_EOF | tee \${PREFIX}/share/applications/pd_added/$package_name.desktop >/dev/null
[Desktop Entry]
Name=${package_name^}
Exec=pdrun "\${run_cmd}"
Terminal=false
Type=Application
Icon=\${HOME}/.appstore/logo/$folder_name/logo.png
StartupWMClass=$package_name
Comment=$package_name
MimeType=x-scheme-handler/$package_name;
Categories=${selected_categories[0]};
DESKTOP_EOF

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
        cat > "$folder_path/uninstall.sh" << EOF
#!/data/data/com.termux/files/usr/bin/bash

package_remove_and_check "$package_name"
EOF
    elif [ "$is_repo_pkg" = "yes" ]; then
        cat > "$folder_path/uninstall.sh" << EOF
#!/data/data/com.termux/files/usr/bin/bash

case "\$selected_distro" in
    "debian"|"ubuntu")
        \$selected_distro remove $package_name -y
        ;;
    "fedora")
        \$selected_distro remove $package_name -y
        ;;
    *)
        echo "Unsupported distribution: \$selected_distro"
        exit 1
        ;;
esac

check_and_delete "\$PREFIX/share/applications/pd_added/$package_name.desktop"
EOF
    else
        if [[ "$download_url" =~ \.AppImage$ ]]; then
            # For AppImage uninstallation
            cat > "$folder_path/uninstall.sh" << EOF
#!/data/data/com.termux/files/usr/bin/bash

check_and_delete "\${distro_path}/opt/AppImageLauncher/$package_name"
check_and_delete "\${distro_path}/usr/share/icons/hicolor/*/apps/$package_name.png"
check_and_delete "\${PREFIX}/share/applications/pd_added/$package_name.desktop"
EOF
        elif [[ "$download_url" =~ \.deb$ ]]; then
            cat > "$folder_path/uninstall.sh" << EOF
if [[ "\$selected_distro" == "ubuntu" ]] || [[ "\$selected_distro" == "debian" ]]; then
distro_run "
sudo apt remove $package_name -y
"
elif [[ "\$selected_distro" == "fedora" ]]; then
distro_run "
rm -rf "/opt/$package_name"
"
else
    print_failed "Unsupported distro"
fi
check_and_delete "\${PREFIX}/share/applications/pd_added/signal-desktop-unofficial.desktop"
EOF
        else
            cat > "$folder_path/uninstall.sh" << EOF
#!/data/data/com.termux/files/usr/bin/bash

distro_run "
check_and_delete '${distro_path}/opt/$package_name'
check_and_delete '$PREFIX/share/applications/pd_added/$package_name.desktop'
"
EOF
        fi
    fi
    
    chmod 755 "$folder_path/uninstall.sh"
}

main() {
    # Get app information
    read -p "Enter app name: " app_name
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
        
        read -p "Is it available in the distro's repository? (yes/no): " is_repo_pkg
        is_repo_pkg=$(echo "$is_repo_pkg" | tr '[:upper:]' '[:lower:]')
        
        if [ "$is_repo_pkg" != "yes" ] && [ "$is_repo_pkg" != "y" ]; then
            is_repo_pkg="no"
            read -p "Enter the download URL for the tar file: " download_url
            # Extract version from GitHub URL
            if [[ $download_url =~ /releases/download/(v[0-9]+\.[0-9]+\.[0-9]+)/ ]]; then
                version="${BASH_REMATCH[1]}"
                echo "Detected version: $version"
            else
                read -p "Could not detect version from URL. Please enter version manually: " version
            fi
        else
            is_repo_pkg="yes"
            read -p "Enter version (press Enter for default): " version
            version=${version:-${app_type}_local_version}
        fi
    else
        read -p "Enter version (press Enter for default): " version
        version=${version:-termux_local_version}
    fi
    
    # Get package details
    read -p "Enter package name: " package_name
    
    if [ "$app_type" = "distro" ] && [ "$is_repo_pkg" = "no" ] && [[ ! "$download_url" =~ \.AppImage$ ]] && [[ ! "$download_url" =~ \.deb$ ]]; then
        # For tar archives, set default run command
        run_cmd="/opt/$package_name/$package_name"
    else
        read -p "Enter run command: " run_cmd
    fi

    # Get description
    echo -e "\nEnter app description (press Ctrl+D twice to finish):"
    description=$(cat)
    
    # Select categories
    echo -e "\nAvailable categories:"
    for i in "${!CATEGORIES[@]}"; do
        echo "$((i+1)). ${CATEGORIES[i]}"
    done
    
    selected_categories=()
    while true; do
        read -p $'\nSelect category number (press Enter when done): ' choice
        
        [ -z "$choice" ] && break
        
        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#CATEGORIES[@]}" ]; then
            category="${CATEGORIES[$((choice-1))]}"
            if [[ ! " ${selected_categories[@]} " =~ " ${category} " ]]; then
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
    echo "$description" > "$app_dir/description.txt"
    
    # Create category file
    (IFS=,; echo "${selected_categories[*]}") > "$app_dir/category.txt"
    
    # Create install and uninstall scripts
    create_install_script "$app_dir" "$app_type" "$supported_distro" "$package_name" "$run_cmd" "$(echo $supported_archs | tr ' ' ',')" "$is_repo_pkg" "$download_url"
    create_uninstall_script "$app_dir" "$package_name" "$is_repo_pkg" "$download_url"
    
    # Handle logo
    while true; do
        read -p $'\nEnter path to logo.png: ' logo_path
        
        # Remove quotes if present
        logo_path="${logo_path//[\'\"]/}"
        
        if [ -f "$logo_path" ] && [[ "$logo_path" =~ \.png$ ]]; then
            cp "$logo_path" "$app_dir/logo.png"
            echo "Logo copied successfully"
            break
        else
            echo "Invalid path or not a PNG file"
        fi
    done
    
    echo -e "\nApp '$app_name' created successfully in $app_dir"
}

main "$@" 