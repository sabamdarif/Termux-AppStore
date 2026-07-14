"""Part E — metadata parser compatibility spot-check.

Metadata stays in each app's ``install.sh`` (refactor decision). Part D rewrote
``add-new-app.sh`` to emit much shorter scripts that use the high-level helpers
and carry extra runtime-only header lines (``sha256=``, ``page_url=``,
``appimage_filename=``, ``archtype=$(detect_arch ...)`` etc.).

This test pins the contract: ``update_metadata.get_app_metadata`` must still
recover ``app_type`` / ``run_cmd`` / ``supported_arch`` / ``version`` /
``supported_distro`` / ``package_name`` from the *new* script shapes, and the
new runtime-only lines must never be mistaken for a metadata assignment.

``update_metadata`` imports ``PIL`` at module load, which is a CI-only
dependency, so we stub it before import. The parser only calls into PIL when an
app folder actually contains a logo image; these fixtures deliberately ship none
(``logo_url`` is then ``None``), so the stub is never exercised.
"""

import sys
import types
from pathlib import Path

import pytest

# --- stub PIL so importing the parser does not require Pillow at test time ---
if "PIL" not in sys.modules:
    _pil = types.ModuleType("PIL")
    _image = types.ModuleType("PIL.Image")

    def _unavailable(*_args, **_kwargs):  # pragma: no cover - never hit here
        raise RuntimeError("PIL is stubbed; no image should be opened in tests")

    _image.open = _unavailable
    _pil.Image = _image
    sys.modules["PIL"] = _pil
    sys.modules["PIL.Image"] = _image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import update_metadata  # noqa: E402


# Each case mirrors exactly what add-new-app.sh's gen_* functions write.
NATIVE = """\
#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="firefox"
run_cmd="firefox"
version="termux_local_version"
app_type="native"

package_install_and_check "$package_name"
"""

NATIVE_DEB = """\
#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="refine"
run_cmd="refine"
version="v1.2.3"
app_type="native"
sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
page_url="https://github.com/example/refine"

archtype=$(detect_arch aarch64=arm64 'armv7*=armv7l' arm=armhf)
install_deb_into_termux \\
    "${page_url}/releases/download/${version}/refine_${version#v}_${archtype}.deb"
"""

APPIMAGE = """\
#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="youtube-music"
run_cmd="youtube-music --no-sandbox"
version="v3.7.0"
app_type="distro"
supported_distro="all"
declare -A sha256=(
    ["YouTube-Music-3.7.0-arm64.AppImage"]="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)
page_url="https://github.com/example/youtube-music"

archtype=$(detect_arch aarch64=arm64 'armv7*=armv7l' arm=armhf)
appimage_filename="YouTube-Music-${version#v}-${archtype}.AppImage"
download_file "${page_url}/releases/download/${version}/${appimage_filename}"
install_appimage "$appimage_filename" "youtube-music"
create_desktop_entry \\
    --name "Youtube-music" --pkg "youtube-music" \\
    --exec "youtube-music --no-sandbox" \\
    --wmclass "youtube-music" --comment "youtube-music" \\
    --categories "Network;" \\
    --logo-dir "Youtube-music"
"""

DEB_INTO_DISTRO = """\
#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="vesktop"
run_cmd="vesktop --no-sandbox"
version="v1.5.3"
app_type="distro"
supported_distro="all"
sha256="skip"
page_url="https://github.com/example/vesktop"

archtype=$(detect_arch aarch64=arm64 'armv7*=armv7l' arm=armhf)
filename="vesktop_${version#v}_${archtype}.deb"
install_deb_into_distro \\
    "${page_url}/releases/download/${version}/${filename}" \\
    "${filename}"
create_desktop_entry \\
    --name "Vesktop" --pkg "vesktop" \\
    --exec "vesktop --no-sandbox" \\
    --wmclass "vesktop" --comment "vesktop" \\
    --categories "Network;InstantMessaging;" \\
    --logo-dir "Vesktop"
"""

ARCHIVE_INTO_OPT = """\
#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="windsurf"
run_cmd="/opt/windsurf/windsurf --no-sandbox"
version="v1.10.0"
app_type="distro"
supported_distro="all"
sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
page_url="https://github.com/example/windsurf"

archtype=$(detect_arch aarch64=arm64 'armv7*=armv7l' arm=armhf)
install_archive_into_opt "windsurf" \\
    "${page_url}/releases/download/${version}/windsurf_${version#v}_linux_arm64.tar.gz"
create_desktop_entry \\
    --name "Windsurf" --pkg "windsurf" \\
    --exec "/opt/windsurf/windsurf --no-sandbox" \\
    --wmclass "windsurf" --comment "windsurf" \\
    --categories "Development;" \\
    --logo-dir "Windsurf"
"""

# run_cmd values may themselves contain '=' (e.g. Chromium's
# `--enable-features=Vulkan`, Mpv's `--player-operation-mode=pseudo-gui`). The
# parser must keep the full value, not truncate at the second '='.
EQUALS_IN_VALUE = """\
#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64,arm"
package_name="chromium"
run_cmd="/data/data/com.termux/files/usr/bin/chromium-browser --enable-features=Vulkan"
version="120.0"
app_type="native"

package_install_and_check "$package_name"
"""

DISTRO_REPO = """\
#!/data/data/com.termux/files/usr/bin/bash

supported_arch="aarch64"
package_name="code"
run_cmd="code --no-sandbox"
version="v1.90.0"
app_type="distro"
supported_distro="debian,ubuntu"

# TODO(contributor): this app installs from a custom distro repository.
case "$SELECTED_DISTRO" in
debian | ubuntu)
    pd_package_install_and_check "code"
    ;;
esac
create_desktop_entry \\
    --name "Code" --pkg "code" --exec "code --no-sandbox" \\
    --logo-dir "Code"
"""

CASES = {
    "native": (
        NATIVE,
        {
            "app_type": "native",
            "run_cmd": "firefox",
            "supported_arch": "aarch64,arm",
            "version": "termux_local_version",
            "package_name": "firefox",
        },
    ),
    "native_deb": (
        NATIVE_DEB,
        {
            "app_type": "native",
            "run_cmd": "refine",
            "supported_arch": "aarch64",
            "version": "v1.2.3",
            "package_name": "refine",
        },
    ),
    "appimage": (
        APPIMAGE,
        {
            "app_type": "distro",
            "run_cmd": "youtube-music --no-sandbox",
            "supported_arch": "aarch64",
            "version": "v3.7.0",
            "supported_distro": "all",
            "package_name": "youtube-music",
        },
    ),
    "deb_into_distro": (
        DEB_INTO_DISTRO,
        {
            "app_type": "distro",
            "run_cmd": "vesktop --no-sandbox",
            "supported_arch": "aarch64,arm",
            "version": "v1.5.3",
            "supported_distro": "all",
            "package_name": "vesktop",
        },
    ),
    "archive_into_opt": (
        ARCHIVE_INTO_OPT,
        {
            "app_type": "distro",
            "run_cmd": "/opt/windsurf/windsurf --no-sandbox",
            "supported_arch": "aarch64",
            "version": "v1.10.0",
            "supported_distro": "all",
            "package_name": "windsurf",
        },
    ),
    "distro_repo": (
        DISTRO_REPO,
        {
            "app_type": "distro",
            "run_cmd": "code --no-sandbox",
            "supported_arch": "aarch64",
            "version": "v1.90.0",
            "supported_distro": "debian,ubuntu",
            "package_name": "code",
        },
    ),
    "equals_in_value": (
        EQUALS_IN_VALUE,
        {
            "app_type": "native",
            "run_cmd": "/data/data/com.termux/files/usr/bin/chromium-browser --enable-features=Vulkan",
            "supported_arch": "aarch64,arm",
            "version": "120.0",
            "package_name": "chromium",
        },
    ),
}


def _make_app(tmp_path, name, install_sh):
    app = tmp_path / name
    app.mkdir()
    (app / "install.sh").write_text(install_sh)
    (app / "description").write_text(f"{name} description")
    (app / "category").write_text("Internet")
    return app


@pytest.mark.parametrize("case", sorted(CASES))
def test_new_script_shapes_parse(tmp_path, case):
    install_sh, expected = CASES[case]
    app = _make_app(tmp_path, case, install_sh)

    data = update_metadata.get_app_metadata(app)

    assert data is not None
    for key, value in expected.items():
        assert data.get(key) == value, f"{case}: {key} expected {value!r}, got {data.get(key)!r}"


def test_native_drops_supported_distro(tmp_path):
    # native apps must not carry supported_distro even if a stray line existed.
    app = _make_app(tmp_path, "firefox", NATIVE)
    data = update_metadata.get_app_metadata(app)
    assert "supported_distro" not in data


def test_runtime_only_headers_are_not_parsed_as_metadata(tmp_path):
    # The sha256 / page_url / archtype / helper-call lines must never leak into
    # the parsed metadata under any of the six recognised keys.
    app = _make_app(tmp_path, "youtube-music", APPIMAGE)
    data = update_metadata.get_app_metadata(app)

    parsed = {
        data.get("app_type"),
        data.get("run_cmd"),
        data.get("supported_arch"),
        data.get("version"),
        data.get("supported_distro"),
        data.get("package_name"),
    }
    # No metadata value should be a checksum or a page URL.
    assert "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" not in parsed
    assert not any(isinstance(v, str) and v.startswith("https://") for v in parsed)


# The parser recognises exactly these six header assignments.
PARSED_KEYS = (
    "app_type",
    "run_cmd",
    "supported_arch",
    "version",
    "supported_distro",
    "package_name",
)


def _declared_value(install_text, key):
    """The value a top-level ``key="..."`` header declares, mirroring how the
    parser matches (strip, prefix, split on first ``=``, strip quotes). If the
    script declares the key more than once, the *last* wins — same as the
    parser, which overwrites on each match. Returns None if never declared."""
    value = None
    for line in install_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            value = stripped.split("=", 1)[1].strip().strip("\"'")
    return value


def test_all_shipped_apps_still_parse():
    # Spot-check the whole repo: for every real app, whatever header the script
    # *declares*, the parser must recover with the same value. This is a pure
    # parser-correctness check and is independent of data completeness (some
    # not-yet-migrated apps legitimately omit e.g. package_name).
    root = Path(update_metadata.__file__).resolve().parents[2]
    apps_dir = root / "apps"
    if not apps_dir.is_dir():
        pytest.skip("apps/ directory not found")

    failures = []
    for app in sorted(apps_dir.iterdir()):
        if not app.is_dir() or not (app / "install.sh").exists():
            continue
        install_text = (app / "install.sh").read_text(encoding="utf-8", errors="replace")
        data = update_metadata.get_app_metadata(app)
        if data is None:
            continue  # missing description/category is a separate concern

        for key in PARSED_KEYS:
            declared = _declared_value(install_text, key)
            if declared is None:
                continue  # app does not set this header — nothing to recover
            # native apps intentionally drop supported_distro from the output.
            if key == "supported_distro" and data.get("app_type") == "native":
                continue
            if data.get(key) != declared:
                failures.append(
                    f"{app.name}: {key} declared {declared!r} but parsed {data.get(key)!r}"
                )

    assert not failures, "apps failed metadata parse:\n" + "\n".join(failures)
