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
    
    cat > "$folder_path/install.sh" << EOF
#!/data/data/com.termux/files/usr/bin/bash

supported_arch="$supported_arch"
package_name="$package_name"
run_cmd="$run_cmd"
EOF
    
    if [ "$app_type" = "native" ]; then
        cat >> "$folder_path/install.sh" << 'EOF'
version=termux_local_version
app_type="native"

package_install_and_check "$package_name"
EOF
    else
        cat >> "$folder_path/install.sh" << EOF
version=distro_local_version
app_type="distro"
supported_distro="$supported_distro"

# Check if a distro is selected
if [ -z "\$selected_distro" ]; then
    echo "Error: No distro selected"
    exit 1
fi

# Install based on distro type
case "\$selected_distro" in
    "debian"|"ubuntu")
        \$selected_distro update
        \$selected_distro install $package_name -y
        ;;
    "fedora")
        \$selected_distro install $package_name -y
        ;;
    *)
        echo "Unsupported distribution: \$selected_distro"
        exit 1
        ;;
esac

# Check if installation was successful
if [ \$? -eq 0 ]; then
    echo "Installation successful"
    exit 0
else
    echo "Installation failed"
    exit 1
fi
EOF
    fi
    
    chmod 755 "$folder_path/install.sh"
}

create_uninstall_script() {
    local folder_path="$1"
    local package_name="$2"
    
    cat > "$folder_path/uninstall.sh" << EOF
#!/data/data/com.termux/files/usr/bin/bash

package_remove_and_check "$package_name"
EOF
    
    chmod 755 "$folder_path/uninstall.sh"
}

main() {
    # Get app information
    read -p "Enter app name: " app_name
    folder_name=$(sanitize_folder_name "$app_name")
    
    # Get supported architectures
    supported_archs=$(get_multiple_choices "Enter supported architectures (comma-separated: aarch64,arm,x86,x86_64): " "aarch64" "arm" "x86" "x86_64")
    
    app_type=$(get_valid_input "Enter app type (native/distro): " "native" "distro")
    
    supported_distro="all"
    if [ "$app_type" = "distro" ]; then
        supported_distro=$(get_valid_input "Enter supported distro (debian/ubuntu/fedora/all): " "debian" "ubuntu" "fedora" "all")
    fi
    
    # Get package details
    read -p "Enter package name: " package_name
    read -p "Enter run command: " run_cmd
    
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
    create_install_script "$app_dir" "$app_type" "$supported_distro" "$package_name" "$run_cmd" "$(echo $supported_archs | tr ' ' ',')"
    create_uninstall_script "$app_dir" "$package_name"
    
    # Handle logo
    while true; do
        read -p $'\nEnter path to logo.png (or press Enter to skip): ' logo_path
        
        [ -z "$logo_path" ] && break
        
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