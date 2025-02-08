#!/usr/bin/env python3
import os
import shutil
from pathlib import Path

CATEGORIES = [
    "Accessories",
    "Development",
    "Games",
    "Graphics",
    "Internet",
    "Multimedia",
    "Office",
    "Productivity"
]

def sanitize_folder_name(name):
    """Convert app name to folder name format"""
    # Ensure first letter is uppercase, rest is lowercase
    name = name.strip()
    return name[0].upper() + name[1:].lower().replace(" ", "-")

def get_valid_input(prompt, valid_options):
    """Get user input and validate against options"""
    while True:
        choice = input(prompt).strip()
        if choice in valid_options:
            return choice
        print(f"Invalid choice. Please choose from: {', '.join(valid_options)}")

def get_multiple_choices(prompt, valid_options):
    """Get multiple choices from comma-separated input"""
    while True:
        choices = input(prompt).strip()
        selected = [choice.strip() for choice in choices.split(',')]
        if all(choice in valid_options for choice in selected):
            return selected
        print(f"Invalid choice(s). Please choose from: {', '.join(valid_options)}")

def create_install_script(folder_path, app_info):
    """Create install.sh script based on app type"""
    script_content = '#!/data/data/com.termux/files/usr/bin/bash\n\n'
    script_content += f'supported_arch="{app_info["supported_arch"]}"\n'
    script_content += f'package_name="{app_info["package_name"]}"\n'
    script_content += f'run_cmd="{app_info["run_cmd"]}"\n'
    
    if app_info["app_type"] == "native":
        script_content += 'version=termux_local_version\n'
        script_content += 'app_type="native"\n'
        script_content += f'\npackage_install_and_check "{app_info["package_name"]}"\n'
    else:
        script_content += 'version=distro_local_version\n'
        script_content += 'app_type="distro"\n'
        script_content += f'supported_distro="{app_info["supported_distro"]}"\n\n'
        
        script_content += '# Check if a distro is selected\n'
        script_content += 'if [ -z "$selected_distro" ]; then\n'
        script_content += '    echo "Error: No distro selected"\n'
        script_content += '    exit 1\n'
        script_content += 'fi\n\n'
        
        script_content += '# Install based on distro type\n'
        script_content += 'case "$selected_distro" in\n'
        script_content += '    "debian"|"ubuntu")\n'
        script_content += '        $selected_distro update\n'
        script_content += f'        $selected_distro install {app_info["package_name"]} -y\n'
        script_content += '        ;;\n'
        script_content += '    "fedora")\n'
        script_content += f'        $selected_distro install {app_info["package_name"]} -y\n'
        script_content += '        ;;\n'
        script_content += '    *)\n'
        script_content += '        echo "Unsupported distribution: $selected_distro"\n'
        script_content += '        exit 1\n'
        script_content += '        ;;\n'
        script_content += 'esac\n\n'
        
        script_content += '# Check if installation was successful\n'
        script_content += 'if [ $? -eq 0 ]; then\n'
        script_content += '    echo "Installation successful"\n'
        script_content += '    exit 0\n'
        script_content += 'else\n'
        script_content += '    echo "Installation failed"\n'
        script_content += '    exit 1\n'
        script_content += 'fi\n'
    
    with open(folder_path / "install.sh", "w") as f:
        f.write(script_content)
    os.chmod(folder_path / "install.sh", 0o755)

def create_uninstall_script(folder_path, package_name):
    """Create uninstall.sh script"""
    script_content = '#!/data/data/com.termux/files/usr/bin/bash\n\n'
    script_content += f'package_remove_and_check "{package_name}"\n'
    
    with open(folder_path / "uninstall.sh", "w") as f:
        f.write(script_content)
    os.chmod(folder_path / "uninstall.sh", 0o755)

def main():
    # Get app information
    app_name = input("Enter app name: ").strip()
    folder_name = sanitize_folder_name(app_name)
    
    # Get supported architectures
    supported_archs = get_multiple_choices(
        "Enter supported architectures (comma-separated: aarch64,arm,x86,x86_64): ",
        ["aarch64", "arm", "x86", "x86_64"]
    )
    
    app_type = get_valid_input(
        "Enter app type (native/distro): ",
        ["native", "distro"]
    )
    
    supported_distro = "all"
    if app_type == "distro":
        supported_distro = get_valid_input(
            "Enter supported distro (debian/ubuntu/fedora/all): ",
            ["debian", "ubuntu", "fedora", "all"]
        )
    
    # Get package details
    package_name = input("Enter package name: ").strip()
    run_cmd = input("Enter run command: ").strip()
    
    # Get description
    print("\nEnter app description (press Enter twice to finish):")
    description_lines = []
    while True:
        line = input()
        if line == "" and (not description_lines or description_lines[-1] == ""):
            break
        description_lines.append(line)
    
    # Select categories
    print("\nAvailable categories:")
    for i, category in enumerate(CATEGORIES, 1):
        print(f"{i}. {category}")
    
    selected_categories = []
    while True:
        choice = input("\nSelect category number (press Enter when done): ").strip()
        if not choice:
            break
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(CATEGORIES):
                category = CATEGORIES[idx]
                if category not in selected_categories:
                    selected_categories.append(category)
                    print(f"Added: {category}")
            else:
                print("Invalid category number")
        except ValueError:
            print("Please enter a valid number")
    
    if not selected_categories:
        print("At least one category must be selected")
        return
    
    # Create app directory and files
    apps_dir = Path("apps")
    app_dir = apps_dir / folder_name
    
    try:
        app_dir.mkdir(parents=True, exist_ok=False)
        
        # Create description.txt file
        with open(app_dir / "description.txt", "w") as f:
            f.write("\n".join(description_lines) + "\n")
        
        # Create category file
        with open(app_dir / "category.txt", "w") as f:
            f.write(",".join(selected_categories) + "\n")
        
        # Create install script with supported architectures
        app_info = {
            "app_type": app_type,
            "supported_distro": supported_distro,
            "package_name": package_name,
            "run_cmd": run_cmd,
            "supported_arch": ",".join(supported_archs)  # Add supported architectures
        }
        create_install_script(app_dir, app_info)
        create_uninstall_script(app_dir, package_name)
        
        # Handle logo with improved path handling
        while True:
            logo_path = input("\nEnter path to logo.png (or press Enter to skip): ").strip()
            if not logo_path:
                break
            
            # Remove quotes if present
            logo_path = logo_path.strip("'\"")
            
            logo_path = Path(logo_path)
            if logo_path.exists() and logo_path.suffix.lower() == '.png':
                shutil.copy2(logo_path, app_dir / "logo.png")
                print("Logo copied successfully")
                break
            else:
                print("Invalid path or not a PNG file")
        
        print(f"\nApp '{app_name}' created successfully in {app_dir}")
        
    except FileExistsError:
        print(f"Error: App directory '{folder_name}' already exists")
    except Exception as e:
        print(f"Error creating app: {e}")
        if app_dir.exists():
            shutil.rmtree(app_dir)

if __name__ == "__main__":
    main() 