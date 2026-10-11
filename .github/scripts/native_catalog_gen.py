#!/usr/bin/env python3
"""Generate the Termux-AppStore native repo catalog (on-device asgen alternative).

Replicates the core of the maintainer's patched appstream-generator without
AppStream: finds Termux packages that ship .desktop launchers, downloads their
.deb payloads, extracts desktop metadata + icons, applies the curated
data/native-overrides.json, and emits per-repo/arch JSON catalogs plus a shared
icon zip. Published by .github/workflows/native-catalog.yml as rolling
`native_data` release assets.

Repos:
  x11  — detection via the Debian Contents index (no downloads needed to find
         desktop-carrying packages).
  tur  — no Contents index exists; candidates come from a Depends-based GUI
         shortlist plus overrides; the .deb payload itself is the check, with
         negative caching in the state file.
  main — metadata-only pass: overrides whose package exists in main get an
         entry synthesized from Packages metadata (covers the terminal apps and
         VLC/Transmission-style main-repo apps). No downloads.

Stdlib only. Tested against live mirrors 2026-10-11.

CLI:
  native_catalog_gen.py --state state/native-state.json --out out/
  native_catalog_gen.py --repo x11 --arch aarch64 --limit 20 --dry-run
"""

import argparse
import hashlib
import gzip
import io
import json
import lzma
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

try:
    from compression import zstd as _zstd  # Python 3.14+
except ImportError:  # pragma: no cover - older interpreters
    _zstd = None

REPOS = {
    "x11": {
        "base": "https://packages-cf.termux.dev/apt/termux-x11",
        "dist": "x11",
        "components": ["main"],
        "contents": True,
    },
    "tur": {
        "base": "https://tur.kcubeterm.com",
        "dist": "tur-packages",
        "components": ["tur", "tur-on-device"],
        "contents": False,
        "shortlist": True,
    },
    "main": {
        "base": "https://packages-cf.termux.dev/apt/termux-main",
        "dist": "stable",
        "components": ["main"],
        "contents": False,
        "metadata_only": True,
    },
}
ARCHES = ["aarch64", "arm"]

SKIP_SUFFIXES = ("-dev", "-static", "-dbg", "-doc", "-cross-tools")
SKIP_PREFIXES = ("lib", "python-", "perl-", "ruby-", "texlive-")

# TUR GUI shortlist: packages depending on a GUI toolkit probably ship a GUI.
GUI_DEP_RE = re.compile(
    r"gtk3|gtk4|qt5|qt6-base|fltk|sdl2|wxwidgets|libx11", re.IGNORECASE
)

# Note: no $ anchor — Contents lines carry the package name after the path.
DESKTOP_PATH_RE = re.compile(r"share/applications/[^/ ]+\.desktop")

# Freedesktop -> store category map (first match wins). Store categories:
# Accessories, Development, Games, Graphics, Internet, Multimedia, Office,
# Productivity.
FDESKTOP_CATEGORY_MAP = [
    (("Development",), "Development"),
    (("Game",), "Games"),
    (("Graphics", "Photography"), "Graphics"),
    (
        (
            "Network",
            "WebBrowser",
            "Email",
            "InstantMessaging",
            "FileTransfer",
            "RemoteAccess",
        ),
        "Internet",
    ),
    (
        ("AudioVideo", "Audio", "Video", "Player", "Recorder", "Music"),
        "Multimedia",
    ),
    (("Office",), "Office"),
    (("Education", "Science"), "Productivity"),
    (("Utility", "Settings", "System", "TerminalEmulator"), "Accessories"),
]

# Regex fallback (ported from appstream-gen.py, remapped to store categories).
CATEGORY_PATTERNS = [
    (
        r"^(kalzium|kanagram|khangman|kbruch|kgeography|klettres|kmplot|kstars"
        r"|ktouch|kturtle|kwordquiz|marble|minuet|cantor|kalgebra|artikulate"
        r"|parley|rocs|kig|kiten|blinken|step|gcompris\S*|tuxmath|tuxtyping)\b",
        "Productivity",
    ),
    (r"education|learn|teach|school|flashcard|vocabulary|typing tutor|anki", "Productivity"),
    (r"office|word processor|spreadsheet|presentation|latex|document", "Office"),
    (r"game|puzzle|chess|tetris", "Games"),
    (r"\b(compiler|debugger|interpreter|language|editor|git|sdk)\b", "Development"),
    (r"audio|music|sound|midi|mp3", "Multimedia"),
    (r"video|movie|stream", "Multimedia"),
    (r"image|graphic|photo|font|svg", "Graphics"),
    (r"network|http|ftp|ssh|dns|proxy|mail|irc|download", "Internet"),
    (r"science|math|calculat", "Productivity"),
    (r"terminal|shell|file manager", "Accessories"),
]

EXEC_FIELD_CODE_RE = re.compile(r"%[fFuUdDnNickvm]")
ENV_PREFIX_RE = re.compile(r"^env\s+(\w+=\S+\s+)+")
SH_C_RE = re.compile(r"^(?:ba|z|da)?sh\s+-c\s+[\"']?([^\"']+?)[\"']?$")

ICON_EXTS = (".png", ".svg", ".xpm")
ICON_SIZE_RANK = {"scalable": 4, "128": 3, "64": 2, "48": 1}

USER_AGENT = "termux-appstore-native-catalog-gen/1.0"

VERBOSE = False


def log(msg):
    """Always-on progress log (also unbuffered for live CI output)."""
    print(msg, flush=True)


def vlog(msg):
    """Verbose-only detail log."""
    if VERBOSE:
        print(msg, flush=True)


def elog(msg):
    """Error log (stderr)."""
    print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


def fetch_bytes(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def download(url, dest, expected_sha256=None):
    """Stream-download url to dest; verify sha256 when given. Returns size."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    h = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(req, timeout=600) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            size += len(chunk)
    if expected_sha256 and h.hexdigest().lower() != expected_sha256.lower():
        raise ValueError(f"SHA256 mismatch for {url}")
    return size


# --------------------------------------------------------------------------
# apt metadata parsing (parser ported from appstream-gen.py)
# --------------------------------------------------------------------------


def parse_stanzas(text):
    """Yield {field: value} dicts from a Debian Packages/Contents-style file."""
    st, key = {}, None
    for line in text.splitlines():
        if not line.strip():
            if st:
                yield st
            st, key = {}, None
        elif line[0] in " \t":
            if key:
                st[key] += " " + line.strip()
        else:
            key, _, val = line.partition(":")
            st[key.strip()] = val.strip()
    if st:
        yield st


def fetch_packages(repo, component, arch):
    """Return {pkg_name: stanza} for a repo component."""
    cfg = REPOS[repo]
    url = f"{cfg['base']}/dists/{cfg['dist']}/{component}/binary-{arch}/Packages"
    vlog(f"  fetching Packages: {url}")
    text = fetch_bytes(url).decode("utf-8", errors="replace")
    pkgs = {}
    for st in parse_stanzas(text):
        name = st.get("Package")
        if name and not name.endswith(SKIP_SUFFIXES):
            pkgs[name] = st
    vlog(f"  {component}: {len(pkgs)} packages after skip filters")
    return pkgs


def parse_contents(text):
    """Parse Contents index text -> {pkg: [desktop paths]}.

    Lines look like: ``data/data/.../share/applications/abiword.desktop abiword``
    and may map one file to comma-separated packages (wezterm,wezterm-nightly).
    """
    result = {}
    for line in text.splitlines():
        if not DESKTOP_PATH_RE.search(line):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        path = parts[0]
        for pkg in parts[-1].split(","):
            pkg = pkg.strip()
            if pkg:
                result.setdefault(pkg, []).append(path)
    return result


def fetch_contents_desktop_pkgs(repo, arch):
    """Download and parse Contents-<arch>.gz -> {pkg: [desktop paths]}."""
    cfg = REPOS[repo]
    url = f"{cfg['base']}/dists/{cfg['dist']}/Contents-{arch}.gz"
    vlog(f"  fetching Contents: {url}")
    text = gzip.decompress(fetch_bytes(url)).decode("utf-8", errors="replace")
    result = parse_contents(text)
    vlog(f"  {len(result)} desktop-carrying packages in Contents")
    return result


# --------------------------------------------------------------------------
# .deb payload extraction
# --------------------------------------------------------------------------


def _ar_members(data):
    """Yield (name, offset, size) for each member of an ar archive."""
    if data[:8] != b"!<arch>\n":
        raise ValueError("not an ar archive")
    i = 8
    while i + 60 <= len(data):
        name = data[i : i + 16].decode("ascii", errors="replace").strip()
        try:
            size = int(data[i + 48 : i + 58].decode("ascii").strip())
        except ValueError:
            break
        yield name.rstrip("/"), i + 60, size
        i += 60 + size + (size % 2)


def _decompress_member(raw, name):
    if name.endswith(".xz") or raw[:6] == b"\xfd7zXZ\x00":
        return lzma.decompress(raw)
    if name.endswith(".gz") or raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)
    if name.endswith(".zst") or raw[:4] == b"\x28\xb5\x2f\xfd":
        if _zstd is not None:
            return _zstd.decompress(raw)
        proc = subprocess.run(
            ["zstd", "-dc"], input=raw, capture_output=True, check=True
        )
        return proc.stdout
    return raw


def open_deb_payload(deb_path):
    """Return a tarfile.TarFile for the deb's data archive."""
    data = Path(deb_path).read_bytes()
    for name, off, size in _ar_members(data):
        if name.startswith("data.tar"):
            payload = _decompress_member(data[off : off + size], name)
            return tarfile.open(fileobj=io.BytesIO(payload), mode="r:")
    raise ValueError(f"no data.tar in {deb_path}")


def _norm(member_name):
    return member_name[2:] if member_name.startswith("./") else member_name


def parse_desktop_file(text):
    """Parse the [Desktop Entry] group. Hand-rolled: desktop files have
    duplicate/localized keys that configparser rejects. Localized variants
    (Name[de]=...) are ignored."""
    entry = {}
    in_group = False
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_group = line == "[Desktop Entry]"
            continue
        if not in_group or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if "[" in key:  # localized variant
            continue
        if key not in entry:
            entry[key] = val.strip()
    return entry


def clean_exec(exec_line, fallback):
    """Strip desktop Exec field codes and trivial wrappers."""
    if not exec_line:
        return fallback
    cmd = ENV_PREFIX_RE.sub("", exec_line.strip())
    m = SH_C_RE.match(cmd)
    if m:
        cmd = m.group(1).strip()
    cmd = EXEC_FIELD_CODE_RE.sub("", cmd)
    cmd = " ".join(cmd.split())
    return cmd or fallback


def map_categories(desktop_cats, name, summary):
    """Freedesktop categories -> store categories, with regex fallback."""
    cats = [c for c in (desktop_cats or "").split(";") if c]
    for fd_keys, store_cat in FDESKTOP_CATEGORY_MAP:
        if any(c in fd_keys for c in cats):
            return [store_cat]
    text = (name + " " + summary).lower()
    for pat, cat in CATEGORY_PATTERNS:
        if re.search(pat, text):
            return [cat]
    return ["Accessories"]


_ICON_SEARCH_SIZE_RE = re.compile(
    r"share/icons/hicolor/([^/]+)/apps/([^/]+)$"
)


def find_icon(tf, icon_name, pkg):
    """Find the best icon member for icon_name (or pkg as fallback).

    Mirrors asgen patch 0002: search share/icons/hicolor/<size>/apps then
    share/pixmaps. Prefers scalable > 128 > 64 > 48 px.
    Returns (member_name, ext) or None.
    """
    wanted = {icon_name, pkg} if icon_name else {pkg}
    wanted = {w for w in wanted if w}
    if not wanted:
        return None
    best = None  # (rank, member)
    for member in tf.getnames():
        name = _norm(member)
        stem, ext = os.path.splitext(name)
        if ext.lower() not in ICON_EXTS:
            continue
        base = os.path.splitext(os.path.basename(name))[0]
        if base not in wanted:
            continue
        rank = 0
        m = _ICON_SEARCH_SIZE_RE.search(stem + ext)
        if m:
            rank = 10 + ICON_SIZE_RANK.get(m.group(1).split("x")[0], 0)
        elif "share/pixmaps/" in name:
            rank = 5
        if best is None or rank > best[0]:
            best = (rank, member)
    if best:
        return best[1]
    return None


def find_metainfo_summary(tf, pkg):
    """Return the <summary> from share/metainfo/*.xml, if any."""
    for member in tf.getnames():
        name = _norm(member)
        if "share/metainfo/" not in name or not name.endswith(".xml"):
            continue
        try:
            root = ET.fromstring(tf.extractfile(member).read())
        except Exception:
            continue
        for summ in root.iter("summary"):
            if summ.text and summ.text.strip() and summ.get("{http://www.w3.org/XML/1998/namespace}lang") is None:
                return summ.text.strip()
    return None


def strip_epoch(version):
    """1:2.3-4 -> 2.3-4 (dpkg epochs confuse string version comparison)."""
    return version.split(":", 1)[1] if ":" in version else version


# --------------------------------------------------------------------------
# Entry building
# --------------------------------------------------------------------------


def build_entry_from_package(tf, pkg, stanza, overrides):
    """Extract metadata from an open payload tar. Returns (entry, icon) or
    (None, None) when the package has no usable desktop file."""
    desktop_members = [
        m
        for m in tf.getnames()
        if DESKTOP_PATH_RE.search(_norm(m))
    ]
    parsed = []
    for member in desktop_members:
        try:
            text = tf.extractfile(member).read().decode("utf-8", errors="replace")
        except Exception:
            continue
        d = parse_desktop_file(text)
        if d.get("Type", "Application") != "Application":
            continue
        if d.get("NoDisplay", "").lower() == "true":
            continue
        if d.get("Hidden", "").lower() == "true":
            continue
        parsed.append((member, d))
    if not parsed:
        return None, None

    # Primary desktop: id basename matches pkg name, else first.
    primary = parsed[0]
    for member, d in parsed:
        if os.path.splitext(os.path.basename(_norm(member)))[0].lower() == pkg.lower():
            primary = (member, d)
            break
    _, dtop = primary

    ov = overrides.get(pkg, {})
    folder_name = ov.get("folder_name", pkg)

    name = ov.get("app_name") or dtop.get("Name") or pkg
    description = (
        ov.get("description")
        or dtop.get("Comment")
        or find_metainfo_summary(tf, pkg)
        or stanza.get("Description", "").split("\n")[0]
        or name
    )
    categories = ov.get("categories") or map_categories(
        dtop.get("Categories", ""), name, description
    )
    run_cmd = ov.get("run_cmd") or clean_exec(dtop.get("Exec", ""), pkg)

    icon = None
    icon_member = find_icon(tf, dtop.get("Icon"), pkg)
    if icon_member:
        ext = os.path.splitext(_norm(icon_member))[1].lower()
        ext = ".png" if ext not in (".png", ".svg") else ext
        try:
            icon = (folder_name, ext, tf.extractfile(icon_member).read())
        except Exception:
            icon = None

    entry = {
        "app_name": name,
        "folder_name": folder_name,
        "description": description,
        "categories": categories,
        "app_type": "native-repo",
        "run_cmd": run_cmd,
        "version": strip_epoch(stanza.get("Version", "")),
        "package_name": pkg,
        "install_url": "scripts/native-install.sh",
        "uninstall_url": "scripts/native-uninstall.sh",
    }
    if stanza.get("Homepage"):
        entry["homepage"] = stanza["Homepage"]
    if ov.get("terminal"):
        entry["terminal"] = True
    return entry, icon


def build_entry_metadata_only(pkg, stanza, overrides):
    """Synthesize an entry from Packages metadata + overrides (main-repo pass,
    terminal apps). No desktop file is involved."""
    ov = overrides.get(pkg, {})
    folder_name = ov.get("folder_name", pkg)
    name = ov.get("app_name", pkg)
    description = (
        ov.get("description")
        or stanza.get("Description", "").split("\n")[0]
        or name
    )
    categories = ov.get("categories") or map_categories("", name, description)
    entry = {
        "app_name": name,
        "folder_name": folder_name,
        "description": description,
        "categories": categories,
        "app_type": "native-repo",
        "run_cmd": ov.get("run_cmd") or pkg,
        "version": strip_epoch(stanza.get("Version", "")),
        "package_name": pkg,
        "install_url": "scripts/native-install.sh",
        "uninstall_url": "scripts/native-uninstall.sh",
    }
    if stanza.get("Homepage"):
        entry["homepage"] = stanza["Homepage"]
    if ov.get("terminal"):
        entry["terminal"] = True
    return entry


# --------------------------------------------------------------------------
# Generation pipeline
# --------------------------------------------------------------------------


def load_state(path):
    if path and os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_state(state, path):
    with open(path, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)


def process_repo(repo, arch, overrides, state, icons_dir, tmpdir, limit=None,
                 dry_run=False):
    """Generate entries for one repo/arch. Mutates state and icons_dir.
    Returns the entry list."""
    cfg = REPOS[repo]
    exclude = set(overrides.get("exclude", []))
    ov_pkgs = overrides.get("packages", {})

    log(f"[{repo}/{arch}] starting")
    pkgs = {}
    for comp in cfg["components"]:
        pkgs.update(fetch_packages(repo, comp, arch))
    log(f"[{repo}/{arch}] {len(pkgs)} packages in index")

    entries = {}

    # --- candidate selection ---
    if cfg.get("contents"):
        desktop_pkgs = fetch_contents_desktop_pkgs(repo, arch)
        candidates = set(desktop_pkgs)
        # Overrides whose package has no desktop file still get metadata entries.
        candidates |= set(ov_pkgs)
    elif cfg.get("metadata_only"):
        candidates = set(ov_pkgs)
    else:  # tur: Depends shortlist + overrides
        candidates = {
            n
            for n, st in pkgs.items()
            if GUI_DEP_RE.search(st.get("Depends", ""))
            and not n.startswith(SKIP_PREFIXES)
        }
        candidates |= set(ov_pkgs)

    candidates -= exclude
    missing = sorted(c for c in candidates if c not in pkgs)
    if missing:
        vlog(f"  candidates not in repo index (skipped): {', '.join(missing)}")
    candidates = sorted(c for c in candidates if c in pkgs)
    if limit:
        candidates = candidates[:limit]
    log(f"[{repo}/{arch}] {len(candidates)} candidates to process")

    for i, pkg in enumerate(candidates, 1):
        stanza = pkgs[pkg]
        version = stanza.get("Version", "")

        cached = state.get(pkg, {}).get(repo, {}).get(arch)
        if cached and cached.get("version") == version:
            result = cached.get("result")
        else:
            result = "PENDING"

        if result == "PENDING":
            if cfg.get("metadata_only"):
                vlog(f"  [{i}/{len(candidates)}] {pkg}: metadata-only entry")
                result = build_entry_metadata_only(pkg, stanza, ov_pkgs)
                if repo not in ("x11",):
                    result["repo"] = repo
            else:
                url = f"{cfg['base']}/{stanza['Filename']}"
                deb_path = os.path.join(tmpdir, f"{pkg}_{arch}.deb")
                try:
                    if not dry_run:
                        size_mb = int(stanza.get("Size", 0)) / 1e6
                        log(f"  [{i}/{len(candidates)}] downloading {pkg} {version} ({size_mb:.1f} MB)")
                        download(url, deb_path, stanza.get("SHA256"))
                        tf = open_deb_payload(deb_path)
                        entry, icon = build_entry_from_package(
                            tf, pkg, stanza, ov_pkgs
                        )
                        if entry is None:
                            result = None  # negative cache
                            vlog(f"    {pkg}: no usable desktop file (negative-cached)")
                        else:
                            entry["repo"] = repo
                            result = entry
                            vlog(
                                f"    {pkg}: entry '{entry['app_name']}' "
                                f"v{entry['version']} [{', '.join(entry['categories'])}]"
                            )
                            if icon:
                                folder, ext, data = icon
                                dest_dir = icons_dir / folder
                                dest_dir.mkdir(parents=True, exist_ok=True)
                                (dest_dir / f"logo{ext}").write_bytes(data)
                                vlog(f"    {pkg}: icon -> {folder}/logo{ext}")
                            else:
                                vlog(f"    {pkg}: no icon found")
                    else:
                        log(f"  [{i}/{len(candidates)}] (dry-run) {pkg} {version}")
                        result = {"_dry_run": True, "package_name": pkg}
                except Exception as e:
                    elog(f"  ERROR {pkg}: {e}")
                    result = None
                finally:
                    if os.path.exists(deb_path):
                        os.remove(deb_path)

            state.setdefault(pkg, {}).setdefault(repo, {})[arch] = {
                "version": version,
                "result": result,
            }
        else:
            vlog(f"  [{i}/{len(candidates)}] {pkg}: cached (v{version})")

        if result and not result.get("_dry_run"):
            entries[pkg] = result
        if i % 50 == 0:
            log(f"  [{repo}/{arch}] progress: {i}/{len(candidates)}")

    return list(entries.values())


def bundle_repo_icons(icons_dir):
    """Repo-provided icons (terminal apps, extraction gaps) win over extracted."""
    repo_icons = Path(__file__).resolve().parents[2] / "data" / "icons"
    if not repo_icons.is_dir():
        return
    for folder in sorted(repo_icons.iterdir()):
        if not folder.is_dir():
            continue
        dest = icons_dir / folder.name
        dest.mkdir(parents=True, exist_ok=True)
        for f in folder.iterdir():
            if f.name.startswith("logo."):
                (dest / f.name).write_bytes(f.read_bytes())


def make_icons_zip(icons_dir, out_path):
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(icons_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(icons_dir))


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--state", default="state/native-state.json")
    ap.add_argument("--out", default="out")
    ap.add_argument("--overrides", default=None,
                    help="path to native-overrides.json (default: repo data/)")
    ap.add_argument("--repo", choices=list(REPOS) + ["all"], default="all")
    ap.add_argument("--arch", choices=ARCHES + ["all"], default="all")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="no downloads; print what would be processed")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="log per-package detail (cache hits, icons, skips)")
    args = ap.parse_args()

    # CI runs capture piped output; make prints appear live.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    global VERBOSE
    VERBOSE = args.verbose

    overrides_path = args.overrides or str(
        Path(__file__).resolve().parents[2] / "data" / "native-overrides.json"
    )
    with open(overrides_path) as f:
        overrides = json.load(f)

    state = load_state(args.state)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    icons_dir = out_dir / "icons"
    icons_dir.mkdir(exist_ok=True)

    # Re-seed icons from the previous release state? Icons are rebuilt from the
    # previous icons zip by the workflow (it pre-populates out/icons before
    # calling us), so we only add newly extracted icons here.

    repos = list(REPOS) if args.repo == "all" else [args.repo]
    arches = ARCHES if args.arch == "all" else [args.arch]

    counts = {}
    for repo in repos:
        for arch in arches:
            with tempfile.TemporaryDirectory() as tmpdir:
                entries = process_repo(
                    repo, arch, overrides, state, icons_dir, tmpdir,
                    limit=args.limit, dry_run=args.dry_run,
                )
            counts[f"{repo}-{arch}"] = len(entries)
            log(f"[{repo}/{arch}] done: {len(entries)} entries")
            if not args.dry_run:
                with open(out_dir / f"{repo}-{arch}.json", "w") as f:
                    json.dump(entries, f, indent=2, ensure_ascii=False)

    if not args.dry_run:
        bundle_repo_icons(icons_dir)
        make_icons_zip(icons_dir, out_dir / "native-icons.zip")
        Path(args.state).parent.mkdir(parents=True, exist_ok=True)
        save_state(state, args.state)
        from datetime import datetime, timezone

        with open(out_dir / "native-version.json", "w") as f:
            json.dump(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "catalog_version": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
                    "counts": counts,
                },
                f,
                indent=2,
            )

    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
