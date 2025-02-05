#!/usr/bin/env python3

import os
import json
from pathlib import Path
from PIL import Image

# GitHub repository information
GITHUB_REPO = "sabamdarif/Termux-AppStore"
GITHUB_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"

def compress_image(image_path, min_size=50, max_size=100):
    """
    Compress the image to ensure its dimensions are between min_size and max_size.
    Keeps the aspect ratio intact.
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            
            # Check if resizing is necessary
            if min_size <= width <= max_size and min_size <= height <= max_size:
                print(f"{image_path} is already within the required dimensions.")
                return
            
            # Calculate the new size while maintaining aspect ratio
            aspect_ratio = width / height
            if width > height:  # Landscape orientation
                new_width = max_size if width > max_size else min_size
                new_height = int(new_width / aspect_ratio)
            else:  # Portrait orientation
                new_height = max_size if height > max_size else min_size
                new_width = int(new_height * aspect_ratio)

            # Ensure the resized dimensions are within the min/max range
            new_width = max(min_size, min(new_width, max_size))
            new_height = max(min_size, min(new_height, max_size))
            
            # Resize the image
            resized_img = img.resize((new_width, new_height), Image.ANTIALIAS)
            resized_img.save(image_path, optimize=True)
            print(f"Compressed {image_path} to {new_width}x{new_height}")

    except Exception as e:
        print(f"Error compressing image {image_path}: {str(e)}")


def read_file_content(app_folder, filename):
    """Read content from a file, trying both with and without .txt extension."""
    files = list(app_folder.glob('*'))
    print(f"\nChecking {app_folder.name}:")
    print(f"Available files: {[f.name for f in files]}")
    
    # Try filename without extension
    content = read_single_file(app_folder / filename)
    if content is not None:
        print(f"Found {filename}")
        return content
        
    # Try filename with .txt extension
    content = read_single_file(app_folder / f"{filename}.txt")
    if content is not None:
        print(f"Found {filename}.txt")
        return content
        
    print(f"Could not find {filename} or {filename}.txt")
    return None


def read_single_file(file_path):
    """Read content from a single file if it exists."""
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error reading {file_path}: {str(e)}")
        return None


def get_urls(app_folder_name, app_folder):
    """Generate URLs for install script, uninstall script, and logo."""
    # Format the folder name for URLs by replacing spaces with hyphens
    url_safe_folder_name = app_folder_name.replace(' ', '-')

    # Priority order for logo/icon files
    priority_order = ['logo.png', 'icon.png'] + \
                     [f"logo-{i}.png" for i in range(100)] + \
                     [f"icon-{i}.png" for i in range(100)]

    def get_logo_file():
        """Select the logo file based on priority and size."""
        selected_file = None
        selected_priority = float('inf')
        selected_size = 0

        # Scan for all .png files in the app folder
        for filename in os.listdir(app_folder):
            if filename.endswith('.png'):
                file_path = os.path.join(app_folder, filename)
                file_size = os.path.getsize(file_path)

                if filename in priority_order:
                    file_priority = priority_order.index(filename)
                else:
                    continue

                if (file_priority < selected_priority or
                    (file_priority == selected_priority and file_size > selected_size)):
                    selected_file = filename
                    selected_priority = file_priority
                    selected_size = file_size

        return selected_file

    # Get the selected logo file
    selected_file_name = get_logo_file()

    if selected_file_name:
        logo_path = os.path.join(app_folder, selected_file_name)
        if os.path.exists(logo_path):
            try:
                compress_image(logo_path)
                logo_url = f"{GITHUB_RAW_URL}/apps/{url_safe_folder_name}/{selected_file_name}"
            except Exception as e:
                print(f"Error compressing {logo_path}: {e}")
                logo_url = None
        else:
            print(f'Warning: Logo file {logo_path} does not exist.')
            logo_url = None
    else:
        print('Warning: No suitable image found for logo_url.')
        logo_url = None

    return {
        'install_url': f"{GITHUB_RAW_URL}/apps/{url_safe_folder_name}/install.sh",
        'uninstall_url': f"{GITHUB_RAW_URL}/apps/{url_safe_folder_name}/uninstall.sh",
        'logo_url': logo_url
    }


def get_app_metadata(app_folder):
    """Get metadata for a single app."""
    # Required files
    description = read_file_content(app_folder, 'description')
    categories_str = read_file_content(app_folder, 'category')

    # If category file is missing, assign a default category
    if not categories_str:
        print(f"Warning: Missing category/category.txt for {app_folder.name}. Assigning 'Uncategorized'.")
        categories_str = "Uncategorized"  # Default category

    # Check for required files
    missing = []
    if not description:
        missing.append('description/description.txt')
    if not categories_str:
        missing.append('category/category.txt')

    if missing:
        print(f"Warning: Missing {', '.join(missing)} for {app_folder.name}")
        return None

    # Get URLs for scripts and logo
    urls = get_urls(app_folder.name, app_folder)

    # Create display name by replacing hyphens with spaces
    display_name = app_folder.name.replace('-', ' ')

    # Read metadata from install.sh
    install_sh_path = app_folder / 'install.sh'
    app_type = "unknown"
    run_cmd = None
    metadata = {
        'app_type': None,
        'run_cmd': None,
        'supported_arch': None,
        'version': None,
        'supported_distro': None,
        'package_name': None,  # Add default package_name
        'ubuntu_run_cmd': None,
        'debian_run_cmd': None,
        'fedora_run_cmd': None,
        'archlinux_run_cmd': None
    }
    
    if install_sh_path.exists():
        try:
            with open(install_sh_path, 'r') as f:
                for line in f:
                    # Read basic metadata
                    if line.strip().startswith('app_type='):
                        app_type = line.split('=')[1].strip().strip('"\'')
                        metadata['app_type'] = app_type
                    elif line.strip().startswith('run_cmd='):
                        run_cmd = line.split('=')[1].strip().strip('"\'')
                        metadata['run_cmd'] = run_cmd
                    elif line.strip().startswith('supported_arch='):
                        supported_arch = line.split('=')[1].strip().strip('"\'')
                        metadata['supported_arch'] = supported_arch
                    elif line.strip().startswith('version='):
                        version = line.split('=')[1].strip().strip('"\'')
                        metadata['version'] = version
                    elif line.strip().startswith('supported_distro='):
                        supported_distro = line.split('=')[1].strip().strip('"\'')
                        metadata['supported_distro'] = supported_distro
                    elif line.strip().startswith('package_name='):  # Add package_name check
                        package_name = line.split('=')[1].strip().strip('"\'')
                        metadata['package_name'] = package_name
                    
                    # Add checks for distro-specific run commands
                    elif line.strip().startswith(('ubuntu_run_cmd=', 'debian_run_cmd=', 
                         'fedora_run_cmd=', 'archlinux_run_cmd=')):
                        cmd_type = line.split('=')[0].strip()
                        cmd_value = line.split('=')[1].strip().strip('"\'')
                        metadata[cmd_type] = cmd_value

            # Remove None values from metadata
            metadata = {k: v for k, v in metadata.items() if v is not None}

        except Exception as e:
            print(f"Error reading install.sh from {install_sh_path}: {e}")

    # Create app metadata
    return {
        'app_name': display_name,
        'folder_name': app_folder.name,
        'description': description,
        'categories': [cat.strip() for cat in categories_str.split(',')],
        **metadata,  # Include all metadata fields
        **urls
    }


def update_metadata():
    """Update the apps.json file with metadata from the apps directory."""
    # Get the root directory (repository root)
    root_dir = Path(__file__).resolve().parents[2]
    apps_dir = root_dir / 'apps'
    data_dir = root_dir / 'data'
    data_dir.mkdir(exist_ok=True)

    apps_data = []

    # Scan apps directory
    for app_folder in sorted(apps_dir.iterdir()):
        if not app_folder.is_dir():
            continue

        app_data = get_app_metadata(app_folder)
        if app_data:
            apps_data.append(app_data)

    # Write the updated metadata to apps.json
    output_file = data_dir / 'apps.json'
    with open(output_file, 'w') as f:
        json.dump(apps_data, f, indent=2)

    print(f"\nUpdated {output_file} with {len(apps_data)} apps")


if __name__ == '__main__':
    update_metadata()