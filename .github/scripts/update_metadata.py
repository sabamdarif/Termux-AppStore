import json
import os
from pathlib import Path

from PIL import Image

GITHUB_REPO = "sabamdarif/Termux-AppStore"
GITHUB_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"


def is_svg(file_path):
    """Check if the file is an SVG file."""
    return str(file_path).lower().endswith(".svg")


def compress_image(image_path):
    """
    Compress the image. If max dimension > 128, scale down to 128.
    If 64 < max dimension <= 128, scale down to 64.
    Keeps the aspect ratio intact. Skips SVG files.
    """
    if is_svg(image_path):
        print(f"{image_path} is an SVG file, skipping compression.")
        return

    try:
        with Image.open(image_path) as img:
            width, height = img.size
            max_dim = max(width, height)

            if max_dim >= 128:
                target_max = 128
            elif max_dim >= 64:
                target_max = 64
            else:
                target_max = max_dim

            resample_filter = getattr(Image, "Resampling", Image).LANCZOS

            if target_max == max_dim:
                img.save(image_path, optimize=True)
                print(f"Optimized {image_path} without resizing")
                return

            if width > height:
                new_width = target_max
                new_height = int(height * (target_max / width))
            else:
                new_height = target_max
                new_width = int(width * (target_max / height))

            resized_img = img.resize((new_width, new_height), resample_filter)
            resized_img.save(image_path, optimize=True)
            print(
                f"Compressed {image_path} from {width}x{height} to {new_width}x{new_height}"
            )

    except Exception as e:
        print(f"Error compressing image {image_path}: {str(e)}")


def read_file_content(app_folder, filename):
    """Read content from a file, trying both with and without .txt extension."""
    files = list(app_folder.glob("*"))
    print(f"\nChecking {app_folder.name}:")
    print(f"Available files: {[f.name for f in files]}")

    content = read_single_file(app_folder / filename)
    if content is not None:
        print(f"Found {filename}")
        return content

    content = read_single_file(app_folder / f"{filename}.txt")
    if content is not None:
        print(f"Found {filename}.txt")
        return content

    print(f"Could not find {filename} or {filename}.txt")
    return None


def read_single_file(file_path):
    """Read content from a single file if it exists."""
    try:
        with open(file_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error reading {file_path}: {str(e)}")
        return None


def get_urls(app_folder_name, app_folder):
    """Generate URLs for install script, uninstall script, and logo."""
    url_safe_folder_name = app_folder_name.replace(" ", "-")

    priority_order = (
        ["logo.png", "icon.png", "logo.svg", "icon.svg"]
        + [f"logo-{i}.png" for i in range(100)]
        + [f"icon-{i}.png" for i in range(100)]
        + [f"logo-{i}.svg" for i in range(100)]
        + [f"icon-{i}.svg" for i in range(100)]
    )

    def get_logo_file():
        """Select the logo file based on priority and size."""
        selected_file = None
        selected_priority = float("inf")
        selected_size = 0

        for filename in os.listdir(app_folder):
            if filename.endswith((".png", ".svg")):
                file_path = os.path.join(app_folder, filename)
                file_size = os.path.getsize(file_path)

                if filename in priority_order:
                    file_priority = priority_order.index(filename)
                else:
                    continue

                if file_priority < selected_priority or (
                    file_priority == selected_priority and file_size > selected_size
                ):
                    selected_file = filename
                    selected_priority = file_priority
                    selected_size = file_size

        return selected_file

    selected_file_name = get_logo_file()

    if selected_file_name:
        logo_path = os.path.join(app_folder, selected_file_name)
        if os.path.exists(logo_path):
            try:
                compress_image(logo_path)
                logo_url = (
                    f"{GITHUB_RAW_URL}/apps/{url_safe_folder_name}/{selected_file_name}"
                )
            except Exception as e:
                print(f"Error processing {logo_path}: {e}")
                logo_url = None
        else:
            print(f"Warning: Logo file {logo_path} does not exist.")
            logo_url = None
    else:
        print("Warning: No suitable image found for logo_url.")
        logo_url = None

    return {
        "install_url": f"{GITHUB_RAW_URL}/apps/{url_safe_folder_name}/install.sh",
        "uninstall_url": f"{GITHUB_RAW_URL}/apps/{url_safe_folder_name}/uninstall.sh",
        "logo_url": logo_url,
    }


def get_app_metadata(app_folder):
    """Get metadata for a single app."""
    description = read_file_content(app_folder, "description")
    categories_str = read_file_content(app_folder, "category")

    if not categories_str:
        print(
            f"Warning: Missing category/category.txt for {app_folder.name}. Assigning 'Uncategorized'."
        )
        categories_str = "Uncategorized"  # Default category

    missing = []
    if not description:
        missing.append("description/description.txt")
    if not categories_str:
        missing.append("category/category.txt")

    if missing:
        print(f"Warning: Missing {', '.join(missing)} for {app_folder.name}")
        return None

    urls = get_urls(app_folder.name, app_folder)

    display_name = app_folder.name.replace("-", " ")

    install_sh_path = app_folder / "install.sh"
    app_type = "unknown"
    run_cmd = None
    metadata = {
        "app_type": None,
        "run_cmd": None,
        "supported_arch": None,
        "version": None,
        "supported_distro": None,
        "package_name": None,
    }

    if install_sh_path.exists():
        try:
            with open(install_sh_path, "r") as f:
                for line in f:
                    if line.strip().startswith("app_type="):
                        app_type = line.split("=")[1].strip().strip("\"'")
                        metadata["app_type"] = app_type
                    elif line.strip().startswith("run_cmd="):
                        run_cmd = line.split("=")[1].strip().strip("\"'")
                        metadata["run_cmd"] = run_cmd
                    elif line.strip().startswith("supported_arch="):
                        supported_arch = line.split("=")[1].strip().strip("\"'")
                        metadata["supported_arch"] = supported_arch
                    elif line.strip().startswith("version="):
                        version = line.split("=")[1].strip().strip("\"'")
                        metadata["version"] = version
                    elif line.strip().startswith("supported_distro="):
                        supported_distro = line.split("=")[1].strip().strip("\"'")
                        metadata["supported_distro"] = supported_distro
                    elif line.strip().startswith("package_name="):
                        package_name = line.split("=")[1].strip().strip("\"'")
                        metadata["package_name"] = package_name

            if metadata.get("app_type") == "native":
                metadata.pop("supported_distro", None)

            metadata = {k: v for k, v in metadata.items() if v is not None}

        except Exception as e:
            print(f"Error reading install.sh from {install_sh_path}: {e}")

    return {
        "app_name": display_name,
        "folder_name": app_folder.name,
        "description": description,
        "categories": [cat.strip() for cat in categories_str.split(",")],
        **metadata,  # Include all metadata fields
        **urls,
    }


def update_metadata():
    """Update the apps.json file with metadata from the apps directory."""

    root_dir = Path(__file__).resolve().parents[2]
    apps_dir = root_dir / "apps"
    data_dir = root_dir / "data"
    data_dir.mkdir(exist_ok=True)

    apps_data = []

    for app_folder in sorted(apps_dir.iterdir()):
        if not app_folder.is_dir():
            continue

        app_data = get_app_metadata(app_folder)
        if app_data:
            apps_data.append(app_data)

    output_file = data_dir / "apps.json"

    updated_apps = []
    if output_file.exists():
        try:
            with open(output_file, "r") as f:
                old_data = json.load(f)
            old_versions = {app["folder_name"]: app.get("version") for app in old_data}
            for app in apps_data:
                folder_name = app["folder_name"]
                new_version = app.get("version")
                old_version = old_versions.get(folder_name)
                if old_version and new_version and old_version != new_version:
                    updated_apps.append((folder_name, old_version, new_version))
                elif not old_version and new_version:
                    updated_apps.append((folder_name, "new", new_version))
        except Exception as e:
            print(f"Error reading old apps.json: {e}")

    if updated_apps:
        with open(root_dir / "updated_apps.txt", "w") as f:
            for folder, old, new in updated_apps:
                f.write(f"- {folder}: {old} -> {new}\n")

    with open(output_file, "w") as f:
        json.dump(apps_data, f, indent=2)

    print(f"\nUpdated {output_file} with {len(apps_data)} apps")


if __name__ == "__main__":
    update_metadata()
